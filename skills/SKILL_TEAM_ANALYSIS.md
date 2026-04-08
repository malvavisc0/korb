# Skill: Team Analysis

Produce a **short paragraph** (3–5 sentences) describing a single basketball team's current situation, suitable for display on a webpage next to the team name.

## Prerequisites

- Use the local `korb` CLI package in this workspace.
- The CLI supports `--json` output.
- Relevant subcommands: `standings`, `team`, `schedule`, `predict`.

## Inputs

| Variable | Required | Default | Description |
|---|---|---|---|
| `TEAM_NAME` | Yes | — | Team name (partial match, case-insensitive) |
| `LIGA_ID` | Yes | — | Liga ID from the DBB URL |
| `LANGUAGE` | No | `en` | Output language: `en`, `de`, or `es` |

> If `TEAM_NAME` or `LIGA_ID` is missing, ask the user before continuing.

---

## Step 1 — Download data (if needed)

Check whether `files/<LIGA_ID>/ergebnisse.html` and `files/<LIGA_ID>/spielplan.html` exist. If not:

```bash
uv run korb --ligaid <LIGA_ID> download
```

---

## Step 2 — Gather data (using JSON outputs)

### Step 2a — Resolve the correct team (name ambiguity)

Because `korb team` accepts a partial team-name match, multiple teams may match `TEAM_NAME`. Use the following resolution rule:

1. Run `standings` in JSON mode.
2. Consider all entries in `standings_json` where the canonical team name contains `TEAM_NAME` (case-insensitive).
3. If there is exactly one match, use it.
4. If there are multiple matches, ask the user which exact canonical team name to analyze.

### Step 2b — Pull season-to-date facts (from `standings --json`)

Run:

```bash
uv run korb --json --ligaid <LIGA_ID> standings
```

From the selected team entry extract:

- **Rank**: `rank = index_in_list + 1` (the JSON list is already sorted)
- **Record (W-L-D)**: `w`, `l`, `d`
- **Standings points**: `pts`
- **Offense/defense identity**: `avg_pf`, `avg_pa`, and **point differential** `diff`

### Step 2c — Pull recent form (from `team --json`)

Run:

```bash
uv run korb --json --ligaid <LIGA_ID> team "<TEAM_NAME>"
```

Important: in JSON mode, the CLI returns **all matching games** and does **not** apply `--last-k` slicing or `--metrics` printing logic.

So to emulate “last 5 games”:

1. Take `team_json["results"]`.
2. Treat it as **newest-first**.
3. Use the first 5 items as the “last 5”. If there are fewer than 5 games, use all available.

Compute:

- **Last-5 record** counts of `result == "W"`, `"L"`, `"D"`
- **Win rate**: `wins / games_used` (draws are not wins)

### Step 2d — Optionally pull predicted finish (only if season is active)

Check pending games:

```bash
uv run korb --json --ligaid <LIGA_ID> schedule --pending
```

- If the returned list is empty: season is finalized → **skip** prediction.
- If pending games exist: run prediction:

```bash
uv run korb --json --ligaid <LIGA_ID> predict
```

From `predict_json["standings"]` extract the team’s **predicted rank** as `index_in_list + 1`.

---

## Step 3 — Compose the paragraph

Write a **single paragraph** (3–5 sentences) that covers:

1. Current league position and record (include rank + W-L-D)
2. Offensive/defensive identity (use `avg_pf`, `avg_pa`, and `diff`)
3. Recent form (last-5 record + win rate)
4. Outlook (if predicted finish exists, mention predicted rank; otherwise give a short forward-looking take based on current form)

Write the paragraph in the selected `LANGUAGE`.

### Tone & style

- Factual but engaging
- Reference specific numbers (e.g., `avg_pf`, `avg_pa`, `diff`)
- No bullet points, no headings, no tables — just a flowing paragraph

---

## Output

Return the paragraph directly. Do **not** save to a file.

