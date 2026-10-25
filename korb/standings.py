"""League standings calculator for DBB (Deutscher Basketball Bund) data.

Calculates and displays standings with points, differentials, and averages.
Target: DBB Version ≤11.50.1-2f7f327 (legacy JSP platform).
"""

from collections import defaultdict
from dataclasses import dataclass
from itertools import groupby
from typing import Final

from korb.core import Game, LeagueInfo, is_forfeit_score, print_header, read_games

WIN_PTS: Final[int] = 2
LOSS_PTS: Final[int] = 0
DRAW_PTS: Final[int] = 1


@dataclass
class TeamStats:
    """Accumulated statistics for one team."""

    gp: int = 0
    w: int = 0
    l: int = 0  # noqa: E741
    d: int = 0
    pf: int = 0
    pa: int = 0
    penalty: int = 0

    @property
    def diff(self) -> int:
        """Point differential (points for minus points against)."""
        return self.pf - self.pa

    @property
    def pts(self) -> int:
        """Total standings points (2 per win, 1 per draw, minus forfeits)."""
        return self.w * WIN_PTS + self.l * LOSS_PTS + self.d * DRAW_PTS + self.penalty

    @property
    def avg_pf(self) -> float:
        """Average points scored per game."""
        return self.pf / self.gp if self.gp else 0.0

    @property
    def avg_pa(self) -> float:
        """Average points allowed per game."""
        return self.pa / self.gp if self.gp else 0.0

    def to_dict(self) -> dict[str, object]:
        """Serializable dict including computed properties."""
        return {
            "gp": self.gp,
            "w": self.w,
            "l": self.l,
            "d": self.d,
            "pf": self.pf,
            "pa": self.pa,
            "penalty": self.penalty,
            "diff": self.diff,
            "pts": self.pts,
            "avg_pf": round(self.avg_pf, 1),
            "avg_pa": round(self.avg_pa, 1),
        }


@dataclass
class Standing:
    """Complete standing entry for a team."""

    name: str
    stats: TeamStats

    def to_dict(self) -> dict[str, object]:
        """Serializable dict."""
        return {"name": self.name, **self.stats.to_dict()}


def record_game(
    teams: dict[str, TeamStats],
    home: str,
    away: str,
    home_score: int,
    away_score: int,
    *,
    forfeit: bool | None = None,
) -> None:
    """Update team stats from a completed or predicted game.

    A DBB forfeit gives the winner 2 points and deducts 1 from the loser.

    Args:
        teams: Dict mapping team names to their stats.
        home: Home team name.
        away: Away team name.
        home_score: Home team score.
        away_score: Away team score.
        forfeit: True if the game was decided as a forfeit; None
            auto-detects a 20:0 or 0:20 result.
    """
    if forfeit is None:
        forfeit = is_forfeit_score(home_score, away_score)
    home_stats = teams.setdefault(home, TeamStats())
    away_stats = teams.setdefault(away, TeamStats())

    home_stats.gp += 1
    home_stats.pf += home_score
    home_stats.pa += away_score

    away_stats.gp += 1
    away_stats.pf += away_score
    away_stats.pa += home_score

    if home_score > away_score:
        home_stats.w += 1
        away_stats.l += 1
        if forfeit:
            away_stats.penalty -= 1
    elif home_score < away_score:
        away_stats.w += 1
        home_stats.l += 1
        if forfeit:
            home_stats.penalty -= 1
    else:
        home_stats.d += 1
        away_stats.d += 1


def _head_to_head(
    games: list[Game], names: set[str]
) -> tuple[dict[str, int], dict[str, int]]:
    """Return points and differential from games between ``names``."""
    stats = {name: TeamStats() for name in names}
    for game in games:
        if game.home in stats and game.away in stats:
            record_game(
                stats,
                game.home,
                game.away,
                game.home_score,
                game.away_score,
                forfeit=game.forfeit,
            )
    return (
        {name: stat.pts for name, stat in stats.items()},
        {name: stat.diff for name, stat in stats.items()},
    )


def _points_split(stats: TeamStats) -> int:
    """Apply DBB's points criterion after overall differential."""
    return stats.pa if stats.diff > 0 else -stats.pf


def rank_standings(standings: list[Standing], games: list[Game]) -> list[Standing]:
    """Rank standings using DBB placement rules.

    Teams are ordered by points, fewer games, head-to-head points,
    head-to-head differential, overall differential, then the DBB
    points-scored/allowed criterion.
    """
    ordered = sorted(standings, key=lambda s: (-s.stats.pts, s.stats.gp))
    ranked: list[Standing] = []
    for _, group in groupby(ordered, key=lambda s: (s.stats.pts, s.stats.gp)):
        tied = list(group)
        if len(tied) > 1:
            h2h_pts, h2h_diff = _head_to_head(games, {s.name for s in tied})
            tied.sort(
                key=lambda s: (
                    -h2h_pts[s.name],
                    -h2h_diff[s.name],
                    -s.stats.diff,
                    _points_split(s.stats),
                    s.name,
                )
            )
        ranked.extend(tied)
    return ranked


def calculate_standings(filepath: str) -> tuple[list[Standing], LeagueInfo]:
    """Calculate league standings from game results.

    Args:
        filepath: HTML results file path.

    Returns:
        Tuple of (standings in DBB placement order, league_info).
    """
    teams: dict[str, TeamStats] = defaultdict(TeamStats)
    games, league_info = read_games(filepath)

    for game in games:
        record_game(
            teams,
            game.home,
            game.away,
            game.home_score,
            game.away_score,
            forfeit=game.forfeit,
        )

    standings = [Standing(name, stats) for name, stats in teams.items()]
    return rank_standings(standings, games), league_info


def print_standings_rows(standings: list[Standing]) -> None:
    """Print the standings column headers and rows."""
    if not standings:
        return

    tw = max(4, max(len(s.name) for s in standings))
    hdr = (
        f"{'#':>2}  {'Team':<{tw}}  "
        f"{'GP':>3} {'W':>3} {'L':>3} {'D':>3}  "
        f"{'PF':>5} {'PA':>5} {'Diff':>6} {'Pts':>4}  "
        f"{'Avg PF':>7} {'Avg PA':>7}"
    )
    print(hdr)
    print("-" * len(hdr))

    for i, s in enumerate(standings, 1):
        d = s.stats.diff
        diff_str = f"+{d}" if d > 0 else str(d)
        print(
            f"{i:>2}  {s.name:<{tw}}  "
            f"{s.stats.gp:>3} {s.stats.w:>3} "
            f"{s.stats.l:>3} {s.stats.d:>3}  "
            f"{s.stats.pf:>5} {s.stats.pa:>5} "
            f"{diff_str:>6} {s.stats.pts:>4}  "
            f"{s.stats.avg_pf:>7.1f} {s.stats.avg_pa:>7.1f}"
        )


def print_table(
    standings: list[Standing],
    league_name: str = "Basketball League",
) -> None:
    """Print formatted standings table.

    Args:
        standings: List of Standing objects to display.
        league_name: League name for header.
    """
    print_header("Standings", league_name)

    if not standings:
        print("No standings data.")
        return

    print_standings_rows(standings)
    print()
