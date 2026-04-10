# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/).

## [0.2.3] — 2026-04-10

### Added

- `skill` subcommand — prints built-in AI skill prompts to stdout.
- `skill --list` / `-l` flag — lists available skill names and filenames.
- `korb/skills/` package with `SKILL_MAP` and `get_skill_text()` using `importlib.resources`.
- Two bundled skills: `analysis` (team deep-dive) and `prediction` (league top-N forecast).
- Skill markdown files now shipped inside the `korb` package (included in pip distributions).

### Changed

- Migrated `skills/` from project root into `korb/skills/` for proper wheel inclusion.

---

## [0.2.2] — 2026-04-09

### Added

- `LeagueInfo` dataclass in `core.py` — bundles league name and Liganr. extracted from HTML.
- All `--json` outputs now include `liga_name`, `liga_number`, and `ligaid` metadata at the top level.
- New `extract_league_info()` function parses both league name and `Liganr.: <number>` from DBB HTML.

### Changed

- `standings`, `team`, `schedule`, `predict`, and `top` JSON responses are now wrapped objects instead of flat lists, with league metadata and a named data key (`standings`, `results`, `schedule`, `predictions`, `top`).
- `read_games()`, `calculate_standings()`, `parse_schedule()`, `get_team_results()`, and `predict_standings()` return `LeagueInfo` instead of a bare `str` league name.

---

## [0.2.1] — 2026-04-08

### Changed

- Download requests now use browser-spoofing headers (Chrome 131 fingerprint) instead of the plain `korb/<version>` User-Agent to avoid basic bot detection.
- Added `gzip`/`deflate` response decompression to match the advertised `Accept-Encoding`.
- Added a random 0.5–1.5 s delay between consecutive HTTP requests to avoid rate-limit triggers.

---

## [0.2.0] — 2026-04-08

### Changed

- `--liganr` renamed to `--ligaid` / `-l` and promoted to global flag.
- `--schedule` / `-s` global flag replaces subcommand-local `--html` on `schedule` and `predict`.
- `download` subcommand now uses global `--ligaid` instead of a positional argument.
- Download logic extracted into reusable `_download()` helper.

### Added

- `--download` / `-d` global flag — downloads fresh data before running any command.

---

## [0.1.0] — 2026-04-08

### Added

- `standings` command — full league table with points, differentials, averages.
- `team` command — game-by-game results, sparklines, bar chart, quality metrics.
- `schedule` command — schedule viewer with back-to-back detection, pending/team filters.
- `predict` command — multiplicative efficiency model for final standings forecast.
- `top` command — quick leaderboard with ASCII bar chart.
- `download` command — fetch HTML data from basketball-bund.net.
- `--json` flag for machine-readable output on all commands.
- `--version` flag.
