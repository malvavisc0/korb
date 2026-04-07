"""League standings calculator for DBB (Deutscher Basketball Bund) data.

Calculates and displays standings with points, differentials, and averages.
Target: DBB Version ≤11.50.0-623b018 (legacy JSP platform).
"""
from collections import defaultdict
from dataclasses import dataclass
from typing import Final, Optional

from korb.core import Game, print_header, read_games

WIN_PTS: Final[int] = 2
LOSS_PTS: Final[int] = 0
DRAW_PTS: Final[int] = 1


@dataclass
class TeamStats:
    """Accumulated statistics for one team."""
    gp: int = 0
    w: int = 0
    l: int = 0
    d: int = 0
    pf: int = 0
    pa: int = 0

    @property
    def diff(self) -> int:
        """Point differential (points for minus points against)."""
        return self.pf - self.pa

    @property
    def pts(self) -> int:
        """Total standings points (2 per win, 1 per draw)."""
        return self.w * WIN_PTS + self.l * LOSS_PTS + self.d * DRAW_PTS

    @property
    def avg_pf(self) -> float:
        """Average points scored per game."""
        return self.pf / self.gp if self.gp else 0.0

    @property
    def avg_pa(self) -> float:
        """Average points allowed per game."""
        return self.pa / self.gp if self.gp else 0.0

    def to_dict(self) -> dict:
        """Serializable dict including computed properties."""
        return {
            "gp": self.gp, "w": self.w, "l": self.l, "d": self.d,
            "pf": self.pf, "pa": self.pa, "diff": self.diff,
            "pts": self.pts, "avg_pf": round(self.avg_pf, 1),
            "avg_pa": round(self.avg_pa, 1),
        }


@dataclass
class Standing:
    """Complete standing entry for a team."""
    name: str
    stats: TeamStats

    def to_dict(self) -> dict:
        """Serializable dict."""
        return {"name": self.name, **self.stats.to_dict()}


def calculate_standings(filepath: Optional[str] = None) -> list[Standing]:
    """Calculate league standings from game results.

    Args:
        filepath: Optional HTML results file path; uses default if None.

    Returns:
        List of Standing objects sorted by pts, diff, pf.
    """
    kwargs = {"filepath": filepath} if filepath else {}
    teams: dict[str, TeamStats] = defaultdict(TeamStats)

    for game in read_games(**kwargs):
        _update_stats(teams, game)

    standings = [Standing(name, stats) for name, stats in teams.items()]
    standings.sort(key=lambda s: (-s.stats.pts, -s.stats.diff, -s.stats.pf))
    return standings


def _update_stats(teams: dict[str, TeamStats], game: Game) -> None:
    """Update team stats from a single game.

    Args:
        teams: Dict mapping team names to their stats.
        game: Completed game to process.
    """
    home = teams[game.home]
    away = teams[game.away]

    home.gp += 1
    home.pf += game.home_score
    home.pa += game.away_score

    away.gp += 1
    away.pf += game.away_score
    away.pa += game.home_score

    if game.home_score > game.away_score:
        home.w += 1
        away.l += 1
    elif game.home_score < game.away_score:
        away.w += 1
        home.l += 1
    else:
        home.d += 1
        away.d += 1


def print_table(standings: list[Standing]) -> None:
    """Print formatted standings table.

    Args:
        standings: List of Standing objects to display.
    """
    print_header("Standings")

    if not standings:
        print("No standings data.")
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

    print()
