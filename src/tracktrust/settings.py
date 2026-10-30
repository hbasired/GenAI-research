"""Settings: config file, recording regions and the aisstream.io API key.

The API key is read from the AISSTREAM_API_KEY environment variable or from a
`.env` file. It is never written to config files, logs or recordings.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover - exercised only on Python 3.10
    import tomli as tomllib

API_KEY_ENV = "AISSTREAM_API_KEY"
CONFIG_ENV = "TRACKTRUST_CONFIG"
DATA_DIR_ENV = "TRACKTRUST_DATA_DIR"
DEFAULT_CONFIG_PATH = Path("config") / "aisstream.toml"


class SettingsError(ValueError):
    """The config file or the API key is missing or malformed."""


@dataclass(frozen=True)
class Region:
    name: str
    box: tuple[tuple[float, float], tuple[float, float]]
    description: str = ""
    enabled: bool = True

    @property
    def lat_min(self) -> float:
        return min(self.box[0][0], self.box[1][0])

    @property
    def lat_max(self) -> float:
        return max(self.box[0][0], self.box[1][0])

    @property
    def lon_min(self) -> float:
        return min(self.box[0][1], self.box[1][1])

    @property
    def lon_max(self) -> float:
        return max(self.box[0][1], self.box[1][1])

    def contains(self, lat: float, lon: float) -> bool:
        return self.lat_min <= lat <= self.lat_max and self.lon_min <= lon <= self.lon_max

    def as_subscription_box(self) -> list[list[float]]:
        return [list(self.box[0]), list(self.box[1])]


@dataclass(frozen=True)
class RecorderSettings:
    stall_timeout_s: float = 300.0
    max_backoff_s: float = 300.0
    auto_compact: bool = True
    status_interval_s: float = 60.0


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    regions: tuple[Region, ...]
    recorder: RecorderSettings = field(default_factory=RecorderSettings)
    config_path: Path | None = None

    @property
    def enabled_regions(self) -> tuple[Region, ...]:
        return tuple(r for r in self.regions if r.enabled)

    @property
    def aisstream_dir(self) -> Path:
        return self.data_dir / "aisstream"

    def region_for(self, lat: float | None, lon: float | None) -> str | None:
        """Name of the first enabled region containing the point, if any."""
        if lat is None or lon is None:
            return None
        for region in self.enabled_regions:
            if region.contains(lat, lon):
                return region.name
        return None

    def select_regions(self, names: list[str] | None) -> Settings:
        """Return a copy where exactly the named regions are enabled."""
        if not names:
            return self
        known = {r.name for r in self.regions}
        unknown = [n for n in names if n not in known]
        if unknown:
            raise SettingsError(
                f"Unknown region(s): {', '.join(unknown)}. Known regions: {', '.join(sorted(known))}"
            )
        wanted = set(names)
        regions = tuple(
            Region(r.name, r.box, r.description, r.name in wanted) for r in self.regions
        )
        return Settings(self.data_dir, regions, self.recorder, self.config_path)


DEFAULT_REGIONS = (
    Region(
        "gulf_hormuz",
        ((22.0, 47.5), (30.5, 62.5)),
        "Arabian Gulf, Strait of Hormuz and Gulf of Oman",
        True,
    ),
)


def _parse_box(name: str, raw: object) -> tuple[tuple[float, float], tuple[float, float]]:
    try:
        (lat1, lon1), (lat2, lon2) = raw  # type: ignore[misc]
        corners = ((float(lat1), float(lon1)), (float(lat2), float(lon2)))
    except (TypeError, ValueError) as exc:
        raise SettingsError(
            f"Region {name!r}: box must be [[lat1, lon1], [lat2, lon2]], got {raw!r}"
        ) from exc
    for lat, lon in corners:
        if not -90.0 <= lat <= 90.0:
            raise SettingsError(f"Region {name!r}: latitude {lat} is outside -90..90")
        if not -180.0 <= lon <= 180.0:
            raise SettingsError(f"Region {name!r}: longitude {lon} is outside -180..180")
    if corners[0][0] == corners[1][0] or corners[0][1] == corners[1][1]:
        raise SettingsError(f"Region {name!r}: box has zero height or width")
    return corners


def _parse_regions(raw_regions: object) -> tuple[Region, ...]:
    if not isinstance(raw_regions, list) or not raw_regions:
        raise SettingsError("The config file must define at least one [[regions]] entry")
    regions = []
    seen = set()
    for item in raw_regions:
        if not isinstance(item, dict) or "name" not in item or "box" not in item:
            raise SettingsError(f"Each [[regions]] entry needs a name and a box, got {item!r}")
        name = str(item["name"])
        if name in seen:
            raise SettingsError(f"Region {name!r} is defined twice")
        seen.add(name)
        regions.append(
            Region(
                name=name,
                box=_parse_box(name, item["box"]),
                description=str(item.get("description", "")),
                enabled=bool(item.get("enabled", True)),
            )
        )
    return tuple(regions)


def load_settings(config_path: str | Path | None = None, data_dir: str | Path | None = None) -> Settings:
    """Load settings from a TOML file, falling back to built-in defaults.

    Lookup order for the file: the `config_path` argument, the TRACKTRUST_CONFIG
    environment variable, then ./config/aisstream.toml. Lookup order for the data
    directory: the `data_dir` argument, TRACKTRUST_DATA_DIR, the file's
    `data_dir`, then ./data.
    """
    path: Path | None = None
    if config_path is not None:
        path = Path(config_path)
        if not path.is_file():
            raise SettingsError(f"Config file not found: {path}")
    elif os.environ.get(CONFIG_ENV):
        path = Path(os.environ[CONFIG_ENV])
        if not path.is_file():
            raise SettingsError(f"{CONFIG_ENV} points to a missing file: {path}")
    elif DEFAULT_CONFIG_PATH.is_file():
        path = DEFAULT_CONFIG_PATH

    raw: dict = {}
    if path is not None:
        try:
            raw = tomllib.loads(path.read_text(encoding="utf-8"))
        except tomllib.TOMLDecodeError as exc:
            raise SettingsError(f"Could not parse {path}: {exc}") from exc

    regions = _parse_regions(raw["regions"]) if "regions" in raw else DEFAULT_REGIONS

    rec_raw = raw.get("recorder", {})
    try:
        recorder = RecorderSettings(
            stall_timeout_s=float(rec_raw.get("stall_timeout_s", 300)),
            max_backoff_s=float(rec_raw.get("max_backoff_s", 300)),
            auto_compact=bool(rec_raw.get("auto_compact", True)),
            status_interval_s=float(rec_raw.get("status_interval_s", 60)),
        )
    except (TypeError, ValueError) as exc:
        raise SettingsError(f"Invalid [recorder] setting: {exc}") from exc
    if recorder.stall_timeout_s <= 0 or recorder.max_backoff_s <= 0 or recorder.status_interval_s <= 0:
        raise SettingsError("[recorder] timeouts and intervals must be positive")

    chosen_dir = data_dir or os.environ.get(DATA_DIR_ENV) or raw.get("data_dir") or "data"
    return Settings(
        data_dir=Path(chosen_dir).expanduser().resolve(),
        regions=regions,
        recorder=recorder,
        config_path=path,
    )


def _read_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if key.startswith("export "):
            key = key[len("export ") :].strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        elif " #" in value:
            value = value.split(" #", 1)[0].rstrip()
        values[key] = value
    return values


def load_api_key(env_file: str | Path | None = None) -> str:
    """Return the aisstream.io API key.

    Lookup order: the AISSTREAM_API_KEY environment variable, then the given
    `.env` file, then ./.env.
    """
    key = os.environ.get(API_KEY_ENV, "").strip()
    source = f"the {API_KEY_ENV} environment variable"
    if not key:
        path = Path(env_file) if env_file is not None else Path(".env")
        if env_file is not None and not path.is_file():
            raise SettingsError(f"Env file not found: {path}")
        if path.is_file():
            key = _read_env_file(path).get(API_KEY_ENV, "").strip()
            source = str(path)
    if not key:
        raise SettingsError(
            "No aisstream.io API key found. Copy .env.example to .env and put your key after "
            f"{API_KEY_ENV}=, or set the {API_KEY_ENV} environment variable."
        )
    if any(ch.isspace() for ch in key) or any(ch in key for ch in "\"'"):
        raise SettingsError(f"The API key from {source} contains spaces or quotes; paste the key only.")
    return key


def mask_key(key: str) -> str:
    """Show only the last four characters of a key, for logs and messages."""
    if len(key) <= 4:
        return "****"
    return "****" + key[-4:]
