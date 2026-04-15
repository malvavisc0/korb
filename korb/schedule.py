"""Schedule parser for DBB (Deutscher Basketball Bund) JSP platform.

Parses game schedule from basketball-bund.net HTML tables.
Target: DBB Version ≤11.50.0-623b018 (legacy JSP platform).
"""

from dataclasses import dataclass
from datetime import datetime
from html.parser import HTMLParser
from typing import Optional

from korb.core import (
    LeagueInfo,
    extract_league_info,
    parse_date,
    print_header,
    read_file_safe,
)


@dataclass
class ScheduledGame:
    """A scheduled game from the HTML schedule."""

    nr: int
    day: int
    date: datetime
    home: str
    away: str
    venue: str
    cancelled: bool

    def to_dict(self) -> dict:
        """Serializable dict."""
        return {
            "nr": self.nr,
            "day": self.day,
            "date": self.date.strftime("%d.%m.%Y %H:%M"),
            "home": self.home,
            "away": self.away,
            "venue": self.venue,
            "cancelled": self.cancelled,
        }


class _HTMLScheduleParser(HTMLParser):
    """Parse basketball-bund.net HTML schedule tables."""

    def __init__(self) -> None:
        """Initialize the parser state."""
        super().__init__()
        self.games: list[ScheduledGame] = []
        self._in_td = False
        self._td_depth = 0
        self._cells: list[str] = []
        self._current_cell = ""
        self._row_cancelled = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, Optional[str]]]) -> None:
        """Track table cell and cancellation markers in HTML.

        Args:
            tag: HTML tag name.
            attrs: List of (name, value) attribute pairs.
        """
        if tag == "td":
            if self._td_depth == 0:
                self._in_td = True
                self._current_cell = ""
            self._td_depth += 1
        elif tag == "strike":
            self._row_cancelled = True
        elif tag == "img":
            for attr_name, attr_val in attrs:
                if attr_name == "title" and attr_val == "Spiel abgesagt":
                    self._row_cancelled = True

    def handle_endtag(self, tag: str) -> None:
        """Finalize cells and rows when closing tags encountered.

        Args:
            tag: HTML tag name.
        """
        if tag == "td":
            self._td_depth -= 1
            if self._td_depth == 0:
                self._cells.append(self._current_cell.strip())
                self._in_td = False
        elif tag == "tr":
            self._finalize_row()
            self._cells = []
            self._row_cancelled = False

    def handle_data(self, data: str) -> None:
        """Accumulate text content within table cells.

        Args:
            data: Text content from HTML.
        """
        if self._in_td and self._td_depth == 1:
            self._current_cell += data

    def _finalize_row(self) -> None:
        """Parse completed row into ScheduledGame if valid."""
        if len(self._cells) < 5:
            return
        try:
            nr = int(self._cells[0])
            day = int(self._cells[1])
            date = parse_date(self._cells[2])
            if not date:
                return
            self.games.append(
                ScheduledGame(
                    nr=nr,
                    day=day,
                    date=date,
                    home=self._cells[3],
                    away=self._cells[4],
                    venue=self._cells[5] if len(self._cells) > 5 else "",
                    cancelled=self._row_cancelled,
                )
            )
        except (ValueError, IndexError):
            pass


def parse_schedule(html_file: str) -> tuple[list[ScheduledGame], LeagueInfo]:
    """Parse HTML file into scheduled games, sorted chronologically.

    Args:
        html_file: Path to HTML schedule file.

    Returns:
        Tuple of (games sorted by date ascending, league_info).
    """
    content = read_file_safe(html_file)
    league_info = extract_league_info(content)
    parser = _HTMLScheduleParser()
    parser.feed(content)
    parser.games.sort(key=lambda g: g.date)
    return parser.games, league_info


def filter_schedule(
    games: list[ScheduledGame],
    show_all: bool = False,
    pending: bool = False,
    team: Optional[str] = None,
) -> list[ScheduledGame]:
    """Filter schedule games by cancellation status, date, and team.

    Args:
        games: List of scheduled games to filter.
        show_all: If True, include cancelled games.
        pending: If True, only include future games.
        team: Optional team name filter (partial match).

    Returns:
        Filtered list of ScheduledGame objects.
    """
    now = datetime.now()
    filtered = [g for g in games if not g.cancelled or show_all]
    if pending:
        filtered = [g for g in filtered if g.date >= now]
    if team:
        t = team.lower()
        filtered = [g for g in filtered if t in g.home.lower() or t in g.away.lower()]
    return filtered


def is_season_finalized(html_path: str) -> tuple[bool, int]:
    """Check if season has no remaining games.

    Args:
        html_path: Path to HTML schedule file.

    Returns:
        Tuple of (is_finalized, pending_count).
    """
    games, _ = parse_schedule(html_path)
    pending = filter_schedule(games, pending=True)
    return len(pending) == 0, len(pending)


def mark_back_to_back(
    games: list[ScheduledGame], threshold_h: int = 36
) -> dict[int, bool]:
    """Mark games where at least one team plays back-to-back.

    Args:
        games: Scheduled games (any order).
        threshold_h: Time window (hours) for back-to-back.

    Returns:
        Dict mapping game index (in the input list) to a boolean.
    """

    threshold_s = threshold_h * 3600
    last_game_ts: dict[str, float] = {}
    b2b: dict[int, bool] = {}

    ordered = sorted(enumerate(games), key=lambda x: x[1].date)
    for idx, g in ordered:
        gt = g.date.timestamp()

        home_b2b = g.home in last_game_ts and (gt - last_game_ts[g.home]) <= threshold_s
        away_b2b = g.away in last_game_ts and (gt - last_game_ts[g.away]) <= threshold_s
        b2b[idx] = bool(home_b2b or away_b2b)

        last_game_ts[g.home] = gt
        last_game_ts[g.away] = gt

    return b2b


def print_schedule(
    games: list[ScheduledGame],
    league_name: str = "Basketball League",
    b2b: bool = False,
) -> None:
    """Print schedule table to stdout.

    Args:
        games: List of scheduled games to display.
        league_name: League name for header.
        b2b: Mark back-to-back fixtures.
    """
    if not games:
        print("No games found.")
        return

    b2b_flags = mark_back_to_back(games) if b2b else {}

    nr_w = max(5, max(len(str(g.nr)) for g in games))
    day_w = max(3, max(len(str(g.day)) for g in games))
    date_w = 16

    home_w = max(
        4,
        max(len(g.home) + (4 if g.cancelled else 0) for g in games),
    )
    away_w = max(
        4,
        max(len(g.away) + (4 if g.cancelled else 0) for g in games),
    )
    venue_w = max(5, max(len(g.venue) for g in games))

    print_header("Schedule", league_name)

    hdr = (
        f"{'Nr.':<{nr_w}}  {'Tag':>{day_w}}  "
        f"{'Datum':<{date_w}}  {'Heim':<{home_w}}  "
        f"{'Gast':<{away_w}}  {'Halle':<{venue_w}}"
    )
    print(hdr)
    print("-" * len(hdr))

    for i, g in enumerate(games):
        home = f"{g.home} [X]" if g.cancelled else g.home
        away = f"{g.away} [X]" if g.cancelled else g.away
        date_str = g.date.strftime("%d.%m.%y %H:%M")
        tag = str(g.day)
        if b2b_flags.get(i, False):
            tag = f"{tag} ⚡"

        print(
            f"{g.nr:<{nr_w}}  {tag:>{day_w}}  "
            f"{date_str:<{date_w}}  {home:<{home_w}}  "
            f"{away:<{away_w}}  {g.venue:<{venue_w}}"
        )

    print()
