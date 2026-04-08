# Skill: League Prediction (Top N)

Produce a **markdown table** of predicted final standings (optionally limited to the top `N` teams) and a **short explanation paragraph** for a basketball league.

## Prerequisites

- Use the local `korb` CLI package in this workspace.
- The CLI supports `--json`.
- Relevant subcommands: `standings`, `schedule`, `predict`, `download`.

## Inputs

| Variable | Required | Default | Description |
|---|---|---|---|
| `LIGA_ID` | Yes | — | Liga ID from the DBB URL |
| `N` | No | all teams | Optionally limit the table to the top N teams |
| `LANGUAGE` | No | `en` | Output language for the explanation paragraph (`en`, `de`, `es`) |

> If `LIGA_ID` is missing, ask the user before continuing.

---

## Step 1 — Download data (if needed)

Check whether `files/<LIGA_ID>/ergebnisse.html` and `files/<LIGA_ID>/spielplan.html` exist. If not:

```bash
uv run korb --ligaid <LIGA_ID> download
```

---

## Step 2 — Read current standings

```bash
uv run korb --json --ligaid <LIGA_ID> standings
```

Store the result list as `standings_json`.

Each entry has: `name`, `w`, `l`, `d`, `pts`, `diff`, `avg_pf`, `avg_pa`, etc.

---

## Step 3 — Check whether the season is already finalized

```bash
uv run korb --json --ligaid <LIGA_ID> schedule --pending
```

Store the returned list as `pending_games`.

- If `pending_games` is empty: the season is finalized → **use current standings** as the final table and skip prediction.
- If `pending_games` is non-empty: proceed to Step 4.

---

## Step 4 — Run prediction (only if season is active)

```bash
uv run korb --json --ligaid <LIGA_ID> predict
```

Extract `pred_json["standings"]` as `final_standings_json`.

If prediction was skipped (season finalized), set `final_standings_json = standings_json`.

---

## Step 5 — Build the markdown table

1. `final_standings_json` is already sorted the same way the CLI prints it.
2. Compute ranks as `rank = index_in_list + 1`.
3. Limit rows to `N` if `N` is provided.
4. Table columns (in this exact order): `#`, `Team`, `W`, `L`, `Pts`, `Diff`.

Use the corresponding fields from each team entry:

- `W` ← `w`
- `L` ← `l`
- `Pts` ← `pts`
- `Diff` ← `diff`

---

## Step 6 — Write the explanation paragraph

Write a **single short paragraph** (2–3 sentences) below the table, in `LANGUAGE`, summarizing:

- Who finishes on top (rank #1 team + their `Pts`)
- Any notable tightness or difference in `Diff`
- Any notable rank separation implied by the table

Keep it brief (caption-like) and avoid bullet points.

---

## Output

Return: (1) the markdown table and (2) the explanation paragraph.

