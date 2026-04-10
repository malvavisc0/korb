<p align="center">
  <strong>🏀 korb</strong><br>
  <em>A CLI toolkit for DBB basketball league analysis</em>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.10%2B-blue?logo=python&amp;logoColor=white" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/uv-package%20manager-blueviolet?logo=uv" alt="uv">
  <img src="https://img.shields.io/badge/deps-zero-brightgreen" alt="Zero dependencies">
  <img src="https://img.shields.io/badge/platform-DBB%20JSP-orange" alt="DBB JSP">
</p>

---

## What is this?

A zero-dependency Python CLI that parses HTML from the **DBB** (Deutscher Basketball Bund) legacy JSP platform and gives you:

- 📊 **Standings** — full league table with points, differentials, averages
- 🏀 **Team drill-down** — game-by-game results, sparklines, quality metrics
- 📅 **Schedule** — with back-to-back detection, filtering, pending games
- 🔮 **Predictions** — efficiency-model-based final standings forecast
- 🥇 **Top N** — quick leaderboard with ASCII bar chart
- 📥 **Download** — fetch fresh HTML data directly from basketball-bund.net
- 🤖 **Skills** — built-in AI skill prompts for team analysis & league prediction
- 🔧 **JSON output** — pipe-friendly `--json` flag for all commands

---

## Finding your Liga ID

The `--ligaid` value comes from the `liga_id` parameter in the DBB league URL:

```
https://www.basketball-bund.net/index.jsp?Action=103&liga_id=51187
                                                           ^^^^^
                                                           this is your liga ID
```

Copy the number after `liga_id=` and pass it to `--ligaid`.

---

## Quick Start

```bash
# Install with uv
uv sync

# Download league data
uv run korb --ligaid 51187 download

# View standings
uv run korb --ligaid 51187 standings

# Download fresh data + predict in one go
uv run korb --ligaid 51187 --download predict
```

---

## Installation

```bash
# Clone and install
git clone https://github.com/malvavisc0/korb && cd korb
uv sync

# Install with dev tools (black, isort)
uv sync --group dev
```

After `uv sync`, the `korb` CLI is available inside the virtual environment. Use `uv run korb` to invoke it, or activate the venv with `source .venv/bin/activate` and run `korb` directly.

---

## Commands

### `download` — Fetch HTML data

```bash
# Download results + schedule for a league
uv run korb --ligaid 12345 download
```

Saves `ergebnisse.html` and `spielplan.html` into `files/<ligaid>/`.

### `standings` — League table

```bash
uv run korb --ligaid 12345 standings
```

```
 #  Team                GP   W   L   D     PF    PA   Diff  Pts   Avg PF  Avg PA
----------------------------------------------------------------------------------
 1  Thunder Academy     12   9   3   0   1248   847   +401   18    104.0    70.6
 2  Riverside Hawks     11   9   2   0    952   668   +284   18     86.5    60.7
 3  Metro Wolves        11   8   3   0    813   694   +119   16     73.9    63.1
...
```

### `team` — Deep dive on a single team

```bash
# Basic results
uv run korb --ligaid 12345 team "Thunder"

# With bar chart + quality metrics for last 5 games
uv run korb --ligaid 12345 team "Thunder" --bars --last-k 5 --metrics
```

### `schedule` — Game calendar

```bash
# All upcoming games
uv run korb --ligaid 12345 schedule --pending

# Filter by team + mark back-to-back ⚡ fixtures
uv run korb --ligaid 12345 schedule --team "Hawks" --pending --b2b

# Include cancelled games
uv run korb --ligaid 12345 schedule --all
```

### `predict` — Forecast final standings

```bash
uv run korb --ligaid 12345 predict
```

Uses a multiplicative efficiency model with recency weighting, recent form blending, home advantage, and back-to-back fatigue modelling.

### `top` — Quick leaderboard

```bash
uv run korb --ligaid 12345 top -n 5
```

### `skill` — Print AI skill prompts

```bash
# List available skills
uv run korb skill --list

# Print a specific skill prompt
uv run korb skill analysis
uv run korb skill prediction
```

Ships two built-in skills: `analysis` (team deep-dive) and `prediction` (league top-N forecast).

### `--download` — Fetch fresh data before any command

```bash
# Download + show standings in one step
uv run korb --ligaid 12345 --download standings

# Download + predict
uv run korb --ligaid 12345 -d predict
```

### `--json` — Machine-readable output

Add `--json` before any subcommand to get JSON instead of tables:

```bash
uv run korb --json --ligaid 12345 standings
uv run korb --json --ligaid 12345 team "Hawks"
uv run korb --json --ligaid 12345 schedule --pending
uv run korb --json --ligaid 12345 predict
uv run korb --json --ligaid 12345 top -n 3
```

---

## CLI Reference

```
$ uv run korb --help

usage: korb [-h] [--version] [--results RESULTS] [--schedule SCHEDULE]
            [--json] [--ligaid LIGAID] [--download]
            {standings,team,schedule,predict,top,download,skill} ...

Basketball league analysis tools

positional arguments:
  {standings,team,schedule,predict,top,download,skill}
    standings           Display league standings
    team                Display results for a team
    schedule            Display game schedule
    predict             Predict final standings
    top                 Show top teams from standings
    download            Download results & schedule HTML
    skill               Print a skill prompt or list available skills

options:
  -h, --help            show this help message and exit
  --version, -V         show program's version number and exit
  --results, -r RESULTS HTML results file path
  --schedule, -s SCHEDULE
                        HTML schedule file path
  --json                Output as JSON instead of formatted tables
  --ligaid, -l LIGAID  Liga ID (e.g. 51491)
  --download, -d        Download latest data before running the command
```

<details>
<summary><code>standings --help</code></summary>

```
usage: korb standings [-h]

options:
  -h, --help  show this help message and exit
```
</details>

<details>
<summary><code>team --help</code></summary>

```
usage: korb team [-h] [--bars] [--last-k LAST_K] [--metrics] name

positional arguments:
  name             Team name (e.g., 'TV 1877 Lauf')

options:
  -h, --help       show this help message and exit
  --bars, -b       Show point differential bar chart
  --last-k LAST_K  Analyze only the most recent K games
  --metrics        Show win-rate + margin quality metrics
```
</details>

<details>
<summary><code>schedule --help</code></summary>

```
usage: korb schedule [-h] [--all] [--pending] [--team TEAM] [--b2b]

options:
  -h, --help       show this help message and exit
  --all, -a        Show cancelled games
  --pending, -p    Show only pending games
  --team, -t TEAM  Filter by team name (partial match)
  --b2b            Mark back-to-back fixtures (≤36h)
```
</details>

<details>
<summary><code>predict --help</code></summary>

```
usage: korb predict [-h]

options:
  -h, --help  show this help message and exit
```
</details>

<details>
<summary><code>top --help</code></summary>

```
usage: korb top [-h] [-n N]

options:
  -h, --help  show this help message and exit
  -n N        How many teams to show (default: 3)
```
</details>

<details>
<summary><code>download --help</code></summary>

```
usage: korb download [-h]

options:
  -h, --help  show this help message and exit
```
</details>

---

## How Predictions Work

The `predict` command estimates final standings using a **multiplicative efficiency model**:

| Factor | How it works |
|---|---|
| **Offensive rating** | Team's scored points vs. league average (>1.0 = above avg) |
| **Defensive rating** | Points allowed vs. league average (>1.0 = worse defense) |
| **Recency weighting** | 60-day half-life — recent games count more |
| **Recent form** | Last 5 games blended at 30% weight into ratings |
| **Home advantage** | 3% scoring boost applied symmetrically |
| **B2B fatigue** | ≤36h between games → 5% offense/defense penalty |
| **New teams** | <3 games → ratings blended toward league average |
| **No draws** | Ties broken by home advantage (basketball has OT) |
| **No double-counting** | Already-played games excluded from schedule scan |

---

## 🧠 Skills

The `skills/` directory contains **reusable AI skill definitions** — structured prompts that can be loaded by an AI assistant (e.g. Roo/Cline) to run analysis workflows using the CLI.

| Skill | Output | Description |
|---|---|---|
| [`SKILL_TEAM_ANALYSIS.md`](skills/SKILL_TEAM_ANALYSIS.md) | Paragraph | Short team summary (position, identity, form, outlook) — ready for a webpage card |
| [`SKILL_LEAGUE_TOP_N_ANALYSIS.md`](skills/SKILL_LEAGUE_TOP_N_ANALYSIS.md) | Table + paragraph | Predicted final standings table with a brief explanation |

Both skills accept a `LANGUAGE` parameter (`en`/`de`/`es`) and return output directly (no file saved). To use a skill, point your AI assistant at the markdown file or load it as a skill definition.

---

## Project Structure

```
├── korb/
│   ├── __init__.py      # Package marker
│   ├── __main__.py      # CLI entry point & download command
│   ├── core.py          # Shared models, HTML parsing, utilities
│   ├── predict.py       # Multiplicative efficiency prediction model
│   ├── schedule.py      # HTML schedule parser & filters
│   ├── standings.py     # Standings calculator
│   └── team.py          # Team results viewer & metrics
├── skills/              # AI skill definitions for automated analysis
├── files/               # Downloaded HTML data (git-ignored)
├── tests/               # Tests
├── pyproject.toml       # Project metadata & uv config
└── README.md
```

**Requirements:** Python 3.10+ · [uv](https://docs.astral.sh/uv/) · No runtime dependencies

> **Note:** Downloaded HTML files and `--ligaid` paths resolve relative to your
> current working directory (`files/<ligaid>/`). Run `korb` from the project root
> or pass explicit `--results` / `--schedule` paths.

### Dev tools

```bash
# Format code
uv run black korb/

# Sort imports
uv run isort korb/
```
