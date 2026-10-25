"""Team results viewer for DBB (Deutscher Basketball Bund) data.

Displays all game results for a specific team with scores,
differentials, and win/loss/draw summary.
Target: DBB Version ≤11.50.1-2f7f327 (legacy JSP platform).
"""

from dataclasses import dataclass
from datetime import datetime
from statistics import pstdev

from korb.core import (
    DATE_FMT,
    Game,
    LeagueInfo,
    normalize_name,
    print_header,
    read_games,
)


@dataclass
class GameResult:
    """Result of a single game from a team's perspective."""

    date: datetime
    opponent: str
    home_away: str
    our_score: int
    opp_score: int
    result: str  # "W", "L", or "D"

    @property
    def diff(self) -> int:
        """Point differential (our score minus opponent score)."""
        return self.our_score - self.opp_score

    def to_dict(self) -> dict[str, object]:
        """Serializable dict including computed properties."""
        return {
            "date": self.date.strftime(DATE_FMT),
            "opponent": self.opponent,
            "home_away": self.home_away,
            "our_score": self.our_score,
            "opp_score": self.opp_score,
            "result": self.result,
            "diff": self.diff,
        }


def _result_code(our: int, opp: int) -> str:
    """Return W/L/D based on scores.

    Args:
        our: Our team's score.
        opp: Opponent's score.

    Returns:
        "W" for win, "L" for loss, "D" for draw.
    """
    if our > opp:
        return "W"
    if our < opp:
        return "L"
    return "D"


def _game_to_result(game: Game, is_home: bool) -> GameResult:
    """Convert a Game to a GameResult from one team's perspective.

    Args:
        game: The game to convert.
        is_home: True if viewing from home team's perspective.

    Returns:
        GameResult with opponent, venue, scores, and result.
    """
    if is_home:
        return GameResult(
            date=game.date,
            opponent=game.away,
            home_away="Home",
            our_score=game.home_score,
            opp_score=game.away_score,
            result=_result_code(game.home_score, game.away_score),
        )
    return GameResult(
        date=game.date,
        opponent=game.home,
        home_away="Away",
        our_score=game.away_score,
        opp_score=game.home_score,
        result=_result_code(game.away_score, game.home_score),
    )


def get_team_results(
    team_name: str, filepath: str
) -> tuple[list[GameResult], LeagueInfo]:
    """Get all game results for a team (case-insensitive partial match).

    Args:
        team_name: Team name to search for (partial match).
        filepath: HTML results file path.

    Returns:
        Tuple of (game results, league_info).
    """
    games, league_info = read_games(filepath)
    results: list[GameResult] = []
    name_lower = normalize_name(team_name)
    if not name_lower:
        return results, league_info

    for game in games:
        if name_lower in normalize_name(game.home):
            results.append(_game_to_result(game, is_home=True))
        elif name_lower in normalize_name(game.away):
            results.append(_game_to_result(game, is_home=False))

    return results, league_info


def _sparkline_char(result: str) -> str:
    """Return sparkline character for result."""
    return {"W": "█", "L": "▄", "D": "─"}.get(result, " ")


def print_results(
    team_name: str,
    results: list[GameResult],
    league_name: str = "Basketball League",
) -> None:
    """Print formatted results table with summary.

    Args:
        team_name: Team name for header display.
        results: List of game results to print.
        league_name: League name for header.
    """
    print_header(f"Team: {team_name}", league_name)

    if not results:
        print(f"No results found for '{team_name}'")
        return

    # Display oldest-first so the row order and sparkline read
    # left-to-right chronologically (results arrive newest-first).
    chronological = list(reversed(results))

    ow = max(3, max(len(r.opponent) for r in chronological))
    hdr = f"{'Opp':<{ow}}  {'H/A':>4}  {'Score':>10}  {'Diff':>6}  {'Result':>6}"
    print(hdr)
    print("-" * len(hdr))

    for r in chronological:
        score_str = f"{r.our_score} - {r.opp_score}"
        diff_str = f"+{r.diff}" if r.diff > 0 else str(r.diff)
        print(
            f"{r.opponent:<{ow}}  {r.home_away:>4}  "
            f"{score_str:>10}  "
            f"{diff_str:>6}  {r.result:>6}"
        )

    # Sparkline row
    sparkline = "".join(_sparkline_char(r.result) for r in chronological)
    print(f"\n{sparkline}  (W=█, L=▄, D=─)")

    _print_summary(chronological)


def _print_summary(results: list[GameResult]) -> None:
    """Print win/loss record and points summary lines."""
    wins = sum(1 for r in results if r.result == "W")
    losses = sum(1 for r in results if r.result == "L")
    draws = sum(1 for r in results if r.result == "D")
    total_pts = sum(r.our_score for r in results)
    opp_pts = sum(r.opp_score for r in results)
    games = len(results)

    record = f"{wins}W - {losses}L"
    if draws:
        record += f" - {draws}D"
    print(f"Summary: {record} ({games} games)")
    print(
        f"Points: {total_pts} scored, {opp_pts} allowed "
        f"(avg: {total_pts / games:.1f} - {opp_pts / games:.1f})"
    )


def _pos_neg_extent(diffs: list[int]) -> tuple[int, int]:
    """Return (max positive diff, abs of max negative diff)."""
    max_pos = max((d for d in diffs if d > 0), default=0)
    max_neg = abs(min((d for d in diffs if d < 0), default=0))
    return max_pos, max_neg


def _fill_run(grid: list[list[str]], col: int, lo: int, hi: int, char: str) -> None:
    """Fill rows [lo, hi) in column `col` with `char`, clamped to grid bounds."""
    for r in range(max(0, lo), min(len(grid), hi)):
        grid[r][col] = char


def _bar_grid(
    diffs: list[int], max_pos: int, max_neg: int, half: int
) -> list[list[str]]:
    """Build the character grid of bar glyphs for each diff column.

    Positive diffs grow upward from the zero line, negative diffs grow
    downward, and zero diffs mark the line itself.
    """
    total = half * 2 + 1
    mid = half
    grid = [["  " for _ in diffs] for _ in range(total)]

    for i, d in enumerate(diffs):
        if d > 0 and max_pos:
            h = max(1, round(d / max_pos * half))
            _fill_run(grid, i, mid - h, mid, "█ ")
        elif d < 0 and max_neg:
            h = max(1, round(abs(d) / max_neg * half))
            _fill_run(grid, i, mid + 1, mid + 1 + h, "█ ")
        elif d == 0:
            grid[mid][i] = "─ "

    return grid


def _trim_rows(grid: list[list[str]], mid: int) -> tuple[int, int]:
    """Return (first, last) non-blank row indices (unchanged loop body)."""
    first = 0
    while first < mid and all(c == "  " for c in grid[first]):
        first += 1
    last = len(grid) - 1
    while last > mid and all(c == "  " for c in grid[last]):
        last -= 1
    return first, last


def _row_labels(max_pos: int, max_neg: int, half: int) -> list[str]:
    """Build y-axis +N/0/-N labels (unchanged loop body)."""
    total = half * 2 + 1
    mid = half
    labels: list[str] = []
    for r in range(total):
        if r == mid:
            labels.append("0")
        elif r < mid:
            labels.append(f"+{round(max_pos * (mid - r) / half)}")
        else:
            labels.append(f"-{round(max_neg * (r - mid) / half)}")
    return labels


def print_bars(results: list[GameResult]) -> None:
    """Print vertical bar chart of point differentials.

    Uses proportional scaling with 6 rows above/below the zero line
    for readable resolution. Empty rows at the extremes are trimmed.

    Args:
        results: List of game results to visualize.
    """
    if not results:
        return

    # Oldest-first so the x-axis (1..N) reads chronologically.
    diffs = [r.diff for r in reversed(results)]
    max_pos, max_neg = _pos_neg_extent(diffs)

    half = 6
    grid = _bar_grid(diffs, max_pos, max_neg, half)
    first, last = _trim_rows(grid, half)
    labels = _row_labels(max_pos, max_neg, half)

    lw = max(len(lb) for lb in labels[first : last + 1])

    for r in range(first, last + 1):
        sep = "┤" if r == half else "│"
        print(f"{labels[r]:>{lw}} {sep} " + "".join(grid[r]))

    bar_w = len(diffs) * 2 + 1
    print(" " * (lw + 1) + "└" + "─" * bar_w)
    nums = " ".join(str(i + 1) for i in range(len(diffs)))
    print(" " * (lw + 2) + " " + nums)


def _last_k(results: list[GameResult], last_k: int | None) -> list[GameResult]:
    """Return the most recent K games.

    `read_games()` yields games newest-first. `get_team_results()` preserves
    that order, so taking `results[:k]` is sufficient.
    """

    if not last_k or last_k <= 0:
        return results
    return results[:last_k]


def _win_rate(results: list[GameResult]) -> float:
    if not results:
        return 0.0
    return sum(1 for r in results if r.result == "W") / len(results)


def _mean(values: list[int]) -> float:
    """Arithmetic mean, or 0.0 for an empty sequence."""
    return sum(values) / len(values) if values else 0.0


def _win_quality(wins: list[int], losses: list[int]) -> tuple[int, int, int]:
    """Return (blowout_wins ≥15, close_wins ≤5, close_losses |diff|≤5)."""
    blowout_wins = sum(1 for d in wins if d >= 15)
    close_wins = sum(1 for d in wins if d <= 5)
    close_losses = sum(1 for d in losses if abs(d) <= 5)
    return blowout_wins, close_wins, close_losses


def _compute_metrics(results: list[GameResult]) -> dict[str, float]:
    """Compute simple distribution metrics from game differentials."""

    diffs = [r.diff for r in results]
    wins = [d for d in diffs if d > 0]
    losses = [d for d in diffs if d < 0]

    blowout_wins, close_wins, close_losses = _win_quality(wins, losses)
    volatility = pstdev(diffs) if len(diffs) >= 2 else 0.0
    extreme_results = sum(1 for d in diffs if abs(d) >= 30)

    return {
        "games": float(len(results)),
        "win_rate": _win_rate(results),
        "blowout_wins": float(blowout_wins),
        "close_wins": float(close_wins),
        "close_losses": float(close_losses),
        "avg_win_margin": _mean(wins),
        "avg_loss_margin": _mean(losses),
        "volatility": float(volatility),
        "extreme_results": float(extreme_results),
    }


def _recent_record(results: list[GameResult]) -> tuple[str, int]:
    """Momentum proxy: return (record string, count) for last 5 games."""
    recent = results[:5]
    if not recent:
        return "", 0
    wins = sum(1 for r in recent if r.result == "W")
    losses = sum(1 for r in recent if r.result == "L")
    draws = sum(1 for r in recent if r.result == "D")
    record = f"{wins}W-{losses}L"
    if draws:
        record += f"-{draws}D"
    return record, len(recent)


def print_metrics(
    results: list[GameResult],
    last_k: int | None = None,
) -> None:
    """Print computed metrics for the (optionally filtered) result list."""

    filtered = _last_k(results, last_k)
    if not filtered:
        print("Metrics: no games to analyze")
        return

    m = _compute_metrics(filtered)
    games = int(m["games"])
    win_rate = m["win_rate"]
    recent_record, recent_games = _recent_record(filtered)

    print("\nMetrics (quality profile)")
    if last_k and last_k > 0:
        print(f"Analyzed: most recent {games} games (newest-first)\n")
    else:
        print(f"Analyzed: {games} games\n")

    print(f"Win rate: {win_rate:.3f}")
    print(
        "Win quality: "
        f"{int(m['blowout_wins'])} blowout (≥15), "
        f"{int(m['close_wins'])} close wins (≤5), "
        f"{int(m['close_losses'])} close losses (|diff|≤5)"
    )
    print(f"Avg win margin (wins only): {m['avg_win_margin']:.1f}")
    print(f"Avg loss margin (losses only): {m['avg_loss_margin']:.1f}")
    print(f"Volatility (stdev of diffs): {m['volatility']:.2f}")
    print(f"Extreme results (|diff|≥30): {int(m['extreme_results'])}")
    if recent_record:
        print(f"Last-{min(5, recent_games)} record: {recent_record}")
