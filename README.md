<p align="center">
  <strong>🏀 korb</strong><br>
  <em>A CLI toolkit for DBB basketball league analysis</em>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.10%2B-blue?logo=python&logoColor=white" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/deps-zero-brightgreen" alt="Zero dependencies">
  <img src="https://img.shields.io/badge/license-MIT-green" alt="MIT License">
</p>

---

**korb** is a zero-dependency Python CLI that parses HTML from the
[DBB](https://www.basketball-bund.net) (Deutscher Basketball Bund) legacy JSP
platform and provides standings, results, schedules, predictions, and more.

## Features

- 📊 **Standings** — full league table with points, differentials, averages
- 🏀 **Team** — game-by-game results, sparklines, quality metrics
- 📋 **Ergebnisse** — all completed game results with optional team filter
- 📅 **Schedule** — with back-to-back detection, filtering, pending games
- 🔮 **Predict** — opponent-adjusted final standings forecast with
  win probabilities
- 🥇 **Top** — quick leaderboard with ASCII bar chart
- 🧪 **Backtest** — chronological holdout metrics for the prediction model
- 📥 **Download** — fetch fresh HTML data directly from basketball-bund.net
- 🔧 **`--json`** — machine-readable output for data commands (not `download`)

## Installation

```bash
# With uv (recommended)
git clone https://github.com/malvavisc0/korb && cd korb
uv sync

# With pip (end-user install)
pip install .
```

After installation, the `korb` CLI is available inside the virtual environment.
Use `uv run korb` to invoke it, or activate the venv first.

## Quick Start

```bash
# Download league data
uv run korb --ligaid 51187 download

# View standings
uv run korb --ligaid 51187 standings

# Download fresh data + predict in one go
uv run korb --ligaid 51187 --download predict
```

## Finding your Liga ID

The `--ligaid` value comes from the `liga_id` parameter in the DBB league URL:

```
https://www.basketball-bund.net/index.jsp?Action=103&liga_id=51187
                                                           ^^^^^
                                                           this is your liga ID
```

## Commands

### `download` — Fetch HTML data

```bash
uv run korb --ligaid 12345 download
uv run korb download --all   # refresh all previously downloaded leagues
```

Saves `ergebnisse.html` and `spielplan.html` into `files/<ligaid>/`.

### `standings` — League table

```bash
uv run korb --ligaid 12345 standings
```

### `ergebnisse` — Game results

```bash
uv run korb --ligaid 12345 ergebnisse
uv run korb --ligaid 12345 ergebnisse --team "Hawks"
```

### `team` — Deep dive on a single team

```bash
uv run korb --ligaid 12345 team "Thunder"
uv run korb --ligaid 12345 team "Thunder" --bars --last-k 5 --metrics
```

### `schedule` — Game calendar

```bash
uv run korb --ligaid 12345 schedule --pending
uv run korb --ligaid 12345 schedule --team "Hawks" --pending --b2b
```

### `predict` — Forecast final standings

```bash
uv run korb --ligaid 12345 predict
uv run korb --ligaid 12345 --json predict
```

### `backtest` — Evaluate the prediction model

```bash
uv run korb --ligaid 12345 backtest
uv run korb --ligaid 12345 backtest --min-train 10
```

Trains on each game's prior results only and reports winner accuracy,
Brier score, score MAE, and score RMSE.

### `top` — Quick leaderboard

```bash
uv run korb --ligaid 12345 top -n 5
```

### Global flags

| Flag | Description |
|---|---|
| `--json` | Output as JSON instead of formatted tables |
| `--download`, `-d` | Fetch fresh data before running the command |
| `--ligaid`, `-l` | Liga ID (resolves file paths automatically) |
| `--results`, `-r` | Explicit path to HTML results file |
| `--schedule`, `-s` | Explicit path to HTML schedule file |
| `--version`, `-V` | Show version |

## How Predictions Work

The `predict` command fits opponent-adjusted ratings and converts them
into a **multiplicative efficiency model**:

| Factor | How it works |
|---|---|
| **Opponent adjustment** | Weighted ridge regression on point differentials |
| **Offensive rating** | Adjusted scoring strength relative to league average (>1.0 = above avg) |
| **Defensive rating** | Adjusted points allowed relative to league average (>1.0 = worse defense) |
| **Recency weighting** | 60-day half-life — recent games count more |
| **Recent form** | Last 5 opponent-adjusted residuals blended at 30% weight |
| **Regularization** | Ridge shrinkage replaces the hard 3-game cutoff |
| **Home advantage** | Fitted from results with a 3% prior |
| **Win probability** | Normal margin model using fitted score volatility |
| **B2B fatigue** | ≤36h between games → 5% offense/defense penalty |
| **No draws** | The higher win probability decides ties |
| **Backtest** | `backtest` evaluates the model chronologically |

## Data Notes

- DBB encodes forfeits as `20:0` / `0:20`; korb counts them as completed
  games, awards the winner 2 points, and deducts 1 point from the loser.
- Struck-through and cancelled rows are skipped.

## Project Structure

```
korb/
├── __init__.py      # Package marker & version
├── __main__.py      # CLI entry point & command handlers
├── backtest.py      # Chronological model evaluation
├── core.py          # Shared models, HTML parsing, utilities
├── download.py      # HTTP downloader, headers, rate limiting
├── ergebnisse.py    # Game results viewer & filter
├── model.py         # Opponent-adjusted ratings & score model
├── predict.py       # Final standings orchestration & output
├── schedule.py      # HTML schedule parser & filters
├── standings.py     # Standings calculator
└── team.py          # Team results viewer & metrics
```

**Requirements:** Python 3.10+ · [uv](https://docs.astral.sh/uv/) · No runtime dependencies

> **Note:** Downloaded HTML files and `--ligaid` paths resolve relative to your
> current working directory (`files/<ligaid>/`). Run `korb` from the project root
> or pass explicit `--results` / `--schedule` paths.

## Development

```bash
# Install with dev tools
uv sync --group dev --locked

# Lint, format & type-check
uv run ruff check korb/ tests/
uv run ruff format korb/ tests/
uv run basedpyright korb

# Run tests
uv run pytest
```

Project conventions are documented in
[`docs/coding-standard.md`](docs/coding-standard.md).

## License

[MIT](LICENSE)
