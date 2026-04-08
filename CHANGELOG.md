# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/).

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
