"""Game results viewer for DBB (Deutscher Basketball Bund) data.

Displays all completed game results for a league with optional team filter.
Target: DBB Version ≤11.50.0-623b018 (legacy JSP platform).
"""

from typing import Optional

from korb.core import Game, print_header


def filter_ergebnisse(games: list[Game], team: Optional[str] = None) -> list[Game]:
    """Filter game results by team name.

    Args:
        games: List of completed games.
        team: Optional team name filter (partial, case-insensitive match).

    Returns:
        Filtered list of Game objects.
    """
    if not team:
        return games
    t = team.lower()
    return [g for g in games if t in g.home.lower() or t in g.away.lower()]


def print_ergebnisse(
    games: list[Game],
    league_name: str = "Basketball League",
) -> None:
    """Print formatted game results table.

    Games are displayed in chronological order (oldest first).

    Args:
        games: List of completed games to display.
        league_name: League name for header.
    """
    print_header("Ergebnisse", league_name)

    if not games:
        print("No game results found.")
        return

    # Sort chronologically ascending (oldest first)
    sorted_games = sorted(games, key=lambda g: g.date)

    date_w = 16
    home_w = max(4, max(len(g.home) for g in sorted_games))
    away_w = max(4, max(len(g.away) for g in sorted_games))
    nr_w = max(3, len(str(len(sorted_games))))

    hdr = (
        f"{'':<{nr_w}}  {'Datum':<{date_w}}  "
        f"{'Heim':<{home_w}}  {'Gast':<{away_w}}  "
        f"{'Ergebnis':>9}  {'Diff':>6}"
    )
    print(hdr)
    print("-" * len(hdr))

    for i, g in enumerate(sorted_games, 1):
        diff = g.home_score - g.away_score
        diff_str = f"+{diff}" if diff > 0 else str(diff)
        score = f"{g.home_score}:{g.away_score}"
        date_str = g.date.strftime("%d.%m.%y %H:%M")

        print(
            f"{i:>{nr_w}}  {date_str:<{date_w}}  "
            f"{g.home:<{home_w}}  {g.away:<{away_w}}  "
            f"{score:>9}  {diff_str:>6}"
        )

    print()
