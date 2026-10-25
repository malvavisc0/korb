# Python Developer AI Agent

## Communication
You are talking to seniors. Be terse — no preamble, no recap, no
hand-holding, no "here's what I did" summaries. State results, not
intentions. Skip explanations unless explicitly asked. Never narrate
tool use. Answer the question; move on.

## Project
korb — a zero-runtime-dependency Python CLI for DBB (Deutscher
Basketball Bund) basketball league analysis. It parses HTML from the
legacy JSP platform at basketball-bund.net (target: DBB Version
≤12.01.1-f733da5) and exposes standings, results, schedules,
predictions, and team metrics. An argparse CLI (`korb/__main__.py`)
dispatches subcommands; `korb/download.py` fetches fresh league HTML
into `files/<ligaid>/`.

## Stack
- Python 3.10+ (CI covers 3.10–3.14), uv, pyproject.toml (hatchling,
  flat `korb/` package layout)
- Zero runtime dependencies: standard library only (`argparse`,
  `html.parser`, `urllib`, `dataclasses`, `zoneinfo`)
- Dev dependencies: pytest, pytest-cov, ruff, basedpyright
- CLI: argparse subcommands in `korb/__main__.py`, entry point
  `korb = "korb.__main__:main"`
- Type checker: **basedpyright** (configured in pyproject; CLI-boundary
  `Any` and style diagnostics disabled)
- Lint/format: **ruff** (line-length 88, target py310 — the minimum
  supported Python)
- Complexity: **radon** (ad hoc via `uvx`)
- Dead code: **vulture** (advisory; no config yet)
- Packaging: hatchling; version lives in `korb/__init__.py`

## Commands
```bash
uv sync --group dev
uv run korb --help
uv run korb --ligaid 12345 download
uv run ruff check --fix korb/ tests/
uv run ruff format korb/ tests/
uv run basedpyright korb
uvx radon cc korb -s --show-closures
uvx vulture korb tests --min-confidence 60
uv run pytest
```
Run `ruff check`, `ruff format --check`, `basedpyright`, and `pytest`
after every change. `basedpyright` must report zero errors; do not add
new warnings. CI runs the same gates plus the radon complexity check.

## Complexity budget
`radon cc` must report **no block ranked C or worse** — every
function/method stays at rank A or B (complexity ≤ 10). This applies to
the whole codebase: a pre-existing C+ block is still a defect and must
be fixed in the same pass (early returns, extract helpers, dispatch
tables). Verify with:
```bash
uvx radon cc korb -s --show-closures | grep -E '\-\s(C|D|E|F)\s'   # must be empty
```

## Dead code
No dead code. Vulture is not configured here, and its hits on
`HTMLParser.handle_*` callbacks, pytest fixtures, and `unittest.mock`
attributes are false positives — never delete those. Treat every other
hit as a suspect: check for a registration site before deleting. Real
dead code (never-read fields, zero-call-site functions) goes out in the
same pass. If vulture becomes a gate, add `[tool.vulture]` to
pyproject.toml and make the default run clean.

## PII
Never use or commit PII — not in code, tests, docs, plans, fixtures,
examples, commit messages, or changelog entries. PII is any real
person's data: names, contact details, message bodies, transcripts,
trace/session ids tied to a person. Rules:

- Tests, docstrings, and examples use fictional identities only.
  Fixtures use synthetic leagues, teams, and scores ("Test
  Bezirksliga", "Team Alpha", `Liganr.: 99999`), never a real league
  export.
- Downloaded HTML contains real league data; it stays in the ignored
  `files/<ligaid>/` tree and never enters git.
- Before committing anything derived from a real export, grep the diff
  for names you saw in it: `git diff | rg -i "<name>"`. If it came from
  an export, it does not go in the repo.

## Priority
Clean, simple, maintainable code. Nothing else.

## Commits
One-line messages only. No body, no trailers.

## Rules
- DRY, KISS
- Zero runtime dependencies — stdlib first, no new dependency without
  an explicit decision
- No unnecessary complexity
- No defensive fallbacks / over-engineering
- Explicit > implicit
- Type hints for all `korb/` code (the hatch-parsed `__version__`
  constant is the exception). Tests follow pytest conventions and need
  not be fully annotated
- Python ≥3.10 syntax and stdlib only (CI runs 3.10 through 3.14)
- PEP 8 (ruff enforces, line-length 88)
- Meaningful names, small functions
- Fail fast and clearly: user-facing errors go to stderr and exit 1.
  Malformed HTML table rows are the one intentional exception: parsers
  skip them so one bad row does not discard an entire league
- No clever tricks
- Docstrings for public APIs
- No unnecessary inline comments
- Use uv for development and CI (never pip / system python). README may
  document pip for end users
- No mutable module-level state. Read-only constants (`HEADERS`, URL
  templates, point values) are fine; never mutate them at runtime
- Module-local helpers take a leading underscore; anything imported by
  production code is public. Tests may import private helpers for
  focused unit tests. `core.py` is the shared-helper home
- No dead code
- No Python file over 600 lines in `korb/` or `tests/`

## Style
Write the simplest correct solution. Delete anything that isn't needed.

## Conventions
- Commands live in `korb/__main__.py`: a `cmd_<name>(args)` handler
  plus an argparse subparser in `main()` wired with
  `set_defaults(func=cmd_<name>)`. Global flags are `--results`,
  `--schedule`, `--json`, `--ligaid`, `--download`.
- Feature modules sit next to the CLI (`standings.py`, `team.py`,
  `schedule.py`, `predict.py`, `ergebnisse.py`, `download.py`); shared
  models, HTML parsing, date/score helpers, and output headers live in
  `core.py`.
- HTML parsing extends the shared public `DBBRowParser`
  (`<td>`/`<tr>`/`<strike>` state machine). Parser changes need a
  fixture in `tests/fixtures/` and a test; cover cancelled rows
  (`<strike>`, `title="Spiel abgesagt"`) and finalized schedules.
- Parsers return `(data, LeagueInfo)`. Every data command's `--json`
  response is a wrapped object built with `_liga_meta(...)` plus a
  named data key: `standings`, `results` (team), `ergebnisse`,
  `schedule`, `predictions`, and `top`. `download` is a side-effect
  command and emits no JSON.
- Data paths resolve as `files/<ligaid>/ergebnisse.html` and
  `files/<ligaid>/spielplan.html`; explicit `--results` / `--schedule`
  win. Use `_resolve_results` / `_resolve_schedule`, not ad hoc paths.
- Downloads live in `korb/download.py` and must keep the
  browser-spoofing headers, gzip/deflate handling, a request timeout,
  and the 1–3 s delay between requests; the legacy host rate-limits.
  Reference: https://www.basketball-bund.net
- Bump `__version__` in `korb/__init__.py` and update `CHANGELOG.md`
  for user-visible changes. Release tags (`v*`) must match the version.
- Tests: one file per module (`tests/test_<module>.py`), pytest with
  coverage enabled by default in `pyproject.toml`. New CLI commands
  need command-level tests, not only module-level unit tests.
