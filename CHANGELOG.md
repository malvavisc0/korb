# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/).

## [0.3.1] — 2026-10-25

### Changed

- Committed `uv.lock`; CI now installs with `uv sync --locked`.
- Release workflow publishes to PyPI before creating the GitHub release
  and pins third-party actions by commit.
- Team JSON results are chronological, matching text output and the
  other data commands.

### Fixed

- Prediction fatigue uses the latest game before each fixture and never
  treats a later game as fatigue.
- Forfeits are excluded from offensive/defensive ratings, recent form,
  and fatigue inputs while remaining in standings.
- Mismatched results and schedule league numbers now exit with an error.
- Downloaded pages must have the expected `Ergebnisse`/`Spielplan`
  title, preventing non-empty error pages from replacing cached data.
- `read_file_safe` reports directories and permission failures cleanly.
- `schedule --json --b2b` now includes per-game `b2b` flags.
- Team-name matching uses Unicode case folding (`Straße` matches
  `STRASSE`).
- Removed the unused, inconsistent `is_season_finalized` helper.

## [0.3.0] — 2026-10-25

### Added

- `korb/download.py` module with a configurable request timeout and
  shared rate-limit helper.
- Coverage for cancelled games marked with `title="Spiel abgesagt"`.
- CLI-level tests for `top`, parser dispatch, download failures, and
  team metrics/bar output.
- Lint, format, type-check, and complexity gates in CI.

### Changed

- Consolidated team-stat updates into `standings.record_game()` and
  standings table rendering into `standings.print_standings_rows()`.
- `predict` now resolves paths through the shared path helpers and
  parses the results file once.
- `__main__.py` HTTP/download code moved out; CLI parser construction
  separated from dispatch.
- `__main__.py` is now included in coverage.
- JSON key documentation now covers the `ergebnisse` response and
  clarifies that `download` emits no JSON.
- `print_metrics()` no longer takes a league name (breaking API change).
- Type annotations added to parser state attributes; ruff targets the
  Python 3.10 floor.
- Updated the supported DBB target to `12.01.1-f733da5`.
- Configured basedpyright for CLI-boundary `Any` values and style
  diagnostics so the type-check gate exits cleanly.

### Removed

- Unreachable draw branches, the unused `print_metrics(league_name)`
  parameter, and the broken Hatch `features = ["dev"]` environment.

### Fixed

- Completed the missing changelog entries for 0.2.4–0.2.9.
- `download --all` now refreshes leagues in numeric order.
- Downloads reject empty responses instead of overwriting cached HTML.
- `schedule --b2b` detects back-to-back games from the full schedule,
  including completed games before a pending fixture, and keeps the
  marker column aligned.
- Result rows with nested tables inside cells now parse correctly.
- Malformed rows with a missing `</tr>` no longer discard later rows.
- `predict` matches completed fixtures by game number, so rescheduled
  games are not counted twice, and treats past-dated unplayed games as
  pending.
- Parsed names collapse repeated whitespace; team filters normalize
  whitespace and reject empty names.
- Standings follow DBB placement rules: fewer games, then head-to-head
  points and differential before overall differential.
- 20:0 and 0:20 results are treated as DBB forfeits and deduct one
  point from the losing team; JSON includes the `penalty` field.
- Cancelled result rows marked with `title="Spiel abgesagt"` are now
  skipped, matching the schedule parser.
- `top -n` and `team --last-k` reject non-positive values instead of
  producing misleading output.

---

## [0.2.9] — 2026-07-26

### Changed

- Fixed result ordering, improved code quality, and added test coverage.
- Stopped tracking `.coverage`.

---

## [0.2.8] — 2026-05-11

### Removed

- `skill` subcommand and `korb/skills/` package.

### Changed

- Replaced black/isort/flake8 with ruff.
- Rewrote `README.md` for public release and cleaned up inline comments
  and `noqa` annotations.

---

## [0.2.7] — 2026-05-06

### Added

- `download --all` / `-a` refreshes all previously downloaded leagues.
- `discover_league_ids()` scans `files/` for downloaded league IDs.

---

## [0.2.6] — 2026-04-23

### Added

- `ergebnisse` subcommand for viewing completed game results.

---

## [0.2.5] — 2026-04-20

### Added

- Game dates in per-team results and JSON output.

---

## [0.2.4] — 2026-04-15

### Changed

- Schedule output sorted by date.
- Dead-code and formatting cleanup.

---

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
