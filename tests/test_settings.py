from pathlib import Path

import pytest

from tracktrust.settings import SettingsError, load_api_key, load_settings, mask_key

REPO_CONFIG = Path(__file__).resolve().parent.parent / "config" / "aisstream.toml"


def test_repo_config_loads_with_gulf_enabled():
    s = load_settings(REPO_CONFIG)
    assert [r.name for r in s.enabled_regions] == ["gulf_hormuz"]
    gulf = s.enabled_regions[0]
    assert gulf.contains(25.0, 55.1)  # Jebel Ali
    assert gulf.contains(24.4, 56.6)  # Sohar
    assert gulf.contains(26.6, 56.3)  # Strait of Hormuz
    assert not gulf.contains(21.5, 39.2)  # Jeddah
    assert s.region_for(25.0, 55.1) == "gulf_hormuz"
    assert s.region_for(None, 55.1) is None
    assert s.data_dir.is_absolute()


def test_select_regions_enables_exactly_those():
    s = load_settings(REPO_CONFIG).select_regions(["red_sea_aden", "sri_lanka"])
    assert [r.name for r in s.enabled_regions] == ["red_sea_aden", "sri_lanka"]
    with pytest.raises(SettingsError, match="Unknown region"):
        load_settings(REPO_CONFIG).select_regions(["atlantis"])


def test_defaults_without_config_file(tmp_path):
    s = load_settings()
    assert s.config_path is None
    assert [r.name for r in s.enabled_regions] == ["gulf_hormuz"]
    assert s.data_dir == (tmp_path / "data").resolve()


def test_data_dir_precedence(tmp_path, monkeypatch):
    monkeypatch.setenv("TRACKTRUST_DATA_DIR", str(tmp_path / "from_env"))
    assert load_settings(REPO_CONFIG).data_dir == (tmp_path / "from_env").resolve()
    assert load_settings(REPO_CONFIG, tmp_path / "arg").data_dir == (tmp_path / "arg").resolve()


@pytest.mark.parametrize(
    "box, message",
    [
        ("[[95.0, 10.0], [96.0, 11.0]]", "latitude"),
        ("[[10.0, 190.0], [11.0, 191.0]]", "longitude"),
        ("[[10.0, 10.0], [10.0, 11.0]]", "zero height"),
        ("[10.0, 10.0]", "box must be"),
    ],
)
def test_bad_boxes_are_rejected(tmp_path, box, message):
    cfg = tmp_path / "c.toml"
    cfg.write_text(f'[[regions]]\nname = "x"\nbox = {box}\n')
    with pytest.raises(SettingsError, match=message):
        load_settings(cfg)


def test_duplicate_region_names_rejected(tmp_path):
    cfg = tmp_path / "c.toml"
    cfg.write_text('[[regions]]\nname="a"\nbox=[[1,1],[2,2]]\n[[regions]]\nname="a"\nbox=[[3,3],[4,4]]\n')
    with pytest.raises(SettingsError, match="twice"):
        load_settings(cfg)


def test_missing_config_file_is_an_error(tmp_path):
    with pytest.raises(SettingsError, match="not found"):
        load_settings(tmp_path / "nope.toml")


def test_api_key_from_env_var(monkeypatch):
    monkeypatch.setenv("AISSTREAM_API_KEY", "  abc123  ")
    assert load_api_key() == "abc123"


@pytest.mark.parametrize(
    "line",
    [
        "AISSTREAM_API_KEY=abc123",
        'AISSTREAM_API_KEY="abc123"',
        "AISSTREAM_API_KEY='abc123'",
        "export AISSTREAM_API_KEY=abc123",
        "AISSTREAM_API_KEY=abc123 # my key",
    ],
)
def test_api_key_from_env_file(tmp_path, line):
    (tmp_path / ".env").write_text(f"# comment\n{line}\nOTHER=1\n")
    assert load_api_key() == "abc123"


def test_env_var_wins_over_env_file(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text("AISSTREAM_API_KEY=fromfile\n")
    monkeypatch.setenv("AISSTREAM_API_KEY", "fromenv")
    assert load_api_key() == "fromenv"


def test_missing_key_explains_what_to_do():
    with pytest.raises(SettingsError, match=r"\.env"):
        load_api_key()


def test_key_with_spaces_rejected(tmp_path):
    (tmp_path / ".env").write_text("AISSTREAM_API_KEY=abc def\n")
    with pytest.raises(SettingsError, match="spaces"):
        load_api_key()


def test_mask_key_shows_last_four_only():
    assert mask_key("93eaa0d68e33f19a3ce951853d5a3d905da9abcd") == "****abcd"
    assert mask_key("abc") == "****"
