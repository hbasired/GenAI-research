# Live AIS recorder (aisstream.io)

The `tracktrust` package records the free aisstream.io live AIS feed for the regions in `config/aisstream.toml` (by default the Arabian Gulf, Strait of Hormuz and Gulf of Oman). It is the first building block of the research code: Paper 1's Gulf case study needs a recording that starts now, because aisstream.io is live only and has no history.

## One-time setup

Needs Python 3.10 or newer. From the repository folder:

```bash
python3 -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
cp .env.example .env                 # Windows: copy .env.example .env
```

Open `.env` and paste your key after the `=`:

```
AISSTREAM_API_KEY=your-key-here
```

`.env` is in `.gitignore`, so the key never goes into git. Never put the key in `config/aisstream.toml`, in a commit, or on the command line.

Check the key:

```bash
tracktrust check-key            # tests the configured regions
tracktrust check-key --world    # tests the key without the region limit
```

| Result | Meaning | Exit code |
|---|---|---|
| `OK: Key accepted ...` | The key works and data is arriving | 0 |
| `PROBLEM: aisstream.io replied: ...` | The key was rejected | 2 |
| `PROBLEM: Connected and subscribed, but no AIS messages ...` | The key was accepted but the area was silent; try `--world` | 3 |
| `PROBLEM: Could not connect ...` | Network problem (firewall, proxy, no internet) | 4 |

## The daily command

```bash
tracktrust record
```

That is the only command you need. It runs until you press Ctrl+C. You can leave it running for days, or start it every morning: restarting is always safe and files are never overwritten.

While it runs it:

- writes every message, exactly as received, to an hourly file;
- reconnects by itself after network drops, server errors and silent periods (it stops for good only if the key is rejected);
- after each UTC midnight, converts the finished day to Parquet tables and writes a coverage summary;
- on the next start, repairs files left by a crash or power cut and processes any finished days that were missed.

Useful options: `--duration 8h` stops after a set time; `--region red_sea_aden` records a different configured region (repeat the option for several); `--no-compact` skips the Parquet step.

Only one recorder can use a data folder at a time. A second one exits with code 3.

## Checking what was recorded

```bash
tracktrust summary                     # today so far
tracktrust summary --date yesterday
tracktrust summary --date 2026-10-30 --json
```

The summary reports messages, vessels, position reports per region, message types, and the share of recorded minutes that had data. It lists two kinds of gaps separately:

- **Silent while recording**: the recorder was running but no messages arrived. Over the sea this can mean no receiver coverage, or vessels switching AIS off. These are the gaps that matter for the research.
- **Recorder not running**: the recorder was stopped or the computer was off. These gaps say nothing about vessels.

Check the summary after the first few days. If `gulf_hormuz` shows few vessels, aisstream.io's volunteer receivers do not cover the Gulf well, and the plan falls back to the Baltic data in the Danish archive (final topic document, Section 13).

## Other commands

| Command | What it does |
|---|---|
| `tracktrust regions` | Lists the configured regions and which ones are on |
| `tracktrust compact` | Converts finished days to Parquet (the recorder does this itself; use it after `--no-compact` or to rebuild with `--force`) |
| `tracktrust recover` | Repairs files left by a crashed recorder (the recorder also does this when it starts) |

## Where the data goes

Everything goes under `data/aisstream/` (change it with `data_dir` in the config, `--data-dir`, or the `TRACKTRUST_DATA_DIR` environment variable). The `data/` folder is in `.gitignore`: recordings are large, and aisstream.io grants no redistribution rights, so they must not be pushed to GitHub. Back them up to an external drive instead.

```
data/aisstream/
  raw/date=2026-10-30/aisstream_20261030T15_<session>.jsonl.gz   one file per UTC hour and run
  events/date=2026-10-30/events_<session>.jsonl                  connects, drops, stalls, heartbeats
  parquet/positions/date=2026-10-30/data.parquet                 one table per message family
  parquet/static/...  parquet/base_stations/...  parquet/aids_to_navigation/...
  parquet/_manifests/date=2026-10-30.json                        raw files used for each day
  summaries/date=2026-10-30.json
  logs/recorder.log
```

Each raw line holds the receive time on your machine (`rx`), a sequence number, the connection number and the server's message unchanged (`msg`). Raw files are the source of truth; Parquet tables can always be rebuilt from them.

The Parquet tables:

| Table | Content |
|---|---|
| `positions` | Position reports (AIS types 1-3, 9, 18, 19, 27): MMSI, latitude, longitude, speed, course, heading, navigational status, the transponder's UTC second and region |
| `static` | Identity and voyage data (types 5, 24 and 19): IMO number, name, call sign, ship type, size, draught, destination and ETA |
| `base_stations` | Shore base stations (type 4). Their positions are fixed, so a jump in a reported position or clock is a direct sign of GNSS interference |
| `aids_to_navigation` | Buoys and beacons (type 21), including virtual aids, which can be spoofed |

Values are stored as transmitted (latitude 91 and longitude 181 still mean "not available"); cleaning belongs to the fidelity stages that come next. Every row has three times: `rx_time` (your machine), `server_time` (aisstream.io) and `ais_second` (the transponder). Keep your computer's clock synchronized (NTP), because receive-time delays are part of the data.

Query with DuckDB, for example:

```sql
SELECT region, count(*) AS reports, count(DISTINCT mmsi) AS vessels
FROM read_parquet('data/aisstream/parquet/positions/*/*.parquet', hive_partitioning = true)
GROUP BY region;
```

## Keeping it running on the DGX Spark or another Linux machine

To record around the clock and restart automatically after a reboot, install the systemd service in `deploy/systemd/` (the file explains the steps). To run it without systemd, use `tmux` or `screen`, start `tracktrust record`, and detach.

## Terms of use

aisstream.io publishes no licence, coverage statement or service level. Use the recording for research only, cite aisstream.io as the source, and do not share or sell the raw data. A commercial TrackTrust product will need a licensed feed (final topic document, Section 1).

## For developers

```bash
pytest
```

The tests run against a local stand-in for the aisstream.io server (`tests/aisstream_mock.py`), so they need no key and no internet. They cover subscription, reconnects, stalls, key rejection, hourly and daily rotation, crash recovery, a full disk, Parquet conversion, summaries and the command line.
