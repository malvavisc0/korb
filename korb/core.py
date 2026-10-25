"""Shared models and utilities for DBB (Deutscher Basketball Bund) analysis.

Provides common types, HTML parsing, and date helpers used across modules.
Target: DBB Version ≤11.50.1-2f7f327 (legacy JSP platform).
"""

import re
import sys
from dataclasses import dataclass
from datetime import datetime
from html.parser import HTMLParser
from typing import Final
from zoneinfo import ZoneInfo

DATE_FMT: Final[str] = "%d.%m.%Y %H:%M"
# DBB schedule times are local German wall-clock times.
LOCAL_TZ: Final[ZoneInfo] = ZoneInfo("Europe/Berlin")
FORFEIT_SCORE: Final[int] = 20
_LEAGUE_FALLBACK: Final[str] = "Basketball League"

# Regex for league name in DBB HTML titles like:
# "Ergebnisse - MFR U12 mix Bezirksliga Nord (U12 ...)"
# "Spielplan - MFR U12 mix Bezirksliga Nord (U12 ...)"
_TITLE_RE = re.compile(r"(?:Ergebnisse|Spielplan)\s*-\s*(.+?)\s*\(")

# Regex for Liganr. inside parenthetical, e.g. "Liganr.: 23182"
_LIGANR_RE = re.compile(r"Liganr\.:\s*(\d+)")


@dataclass
class LeagueInfo:
    """Metadata about a league extracted from DBB HTML."""

    name: str
    number: int | None = None

    def to_dict(self) -> dict[str, object]:
        """Serializable dict."""
        return {"liga_name": self.name, "liga_number": self.number}


@dataclass
class Game:
    """A single completed basketball game."""

    date: datetime
    home: str
    away: str
    home_score: int
    away_score: int
    nr: int | None = None
    forfeit: bool = False


def normalize_whitespace(value: str) -> str:
    """Collapse whitespace runs into single spaces."""
    return " ".join(value.split())


def normalize_name(value: str) -> str:
    """Normalize a team name for case-insensitive matching."""
    return normalize_whitespace(value).lower()


def is_forfeit_score(home_score: int, away_score: int) -> bool:
    """Return True for DBB's 20:0 or 0:20 forfeit score."""
    return (home_score, away_score) in ((FORFEIT_SCORE, 0), (0, FORFEIT_SCORE))


def parse_date(date_str: str | None) -> datetime | None:
    """Parse date string in format 'DD.MM.YYYY HH:MM'.

    Args:
        date_str: Date string to parse, or None.

    Returns:
        Parsed datetime or None if invalid format.
    """
    if date_str is None:
        return None
    try:
        return datetime.strptime(date_str.strip(), DATE_FMT).replace(tzinfo=LOCAL_TZ)
    except ValueError:
        return None


def parse_score(score_str: str | None) -> tuple[int | None, int | None]:
    """Parse score string in format '79 : 75'.

    Args:
        score_str: Score string to parse, or None.

    Returns:
        Tuple of (home_score, away_score) or (None, None) if invalid.
    """
    if not score_str or not score_str.strip():
        return None, None
    parts = score_str.split(":")
    if len(parts) != 2:
        return None, None
    try:
        return int(parts[0].strip()), int(parts[1].strip())
    except ValueError:
        return None, None


def read_file_safe(filepath: str) -> str:
    """Read file with user-friendly error on missing file.

    Args:
        filepath: Path to file to read.

    Returns:
        File contents as string.

    Raises:
        SystemExit: If file not found.
    """
    try:
        with open(filepath, encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        print(f"Error: File not found: {filepath}", file=sys.stderr)
        sys.exit(1)


class DBBRowParser(HTMLParser):
    """Shared table-row state machine for DBB HTML results and schedules."""

    _in_td: bool
    _td_depth: int
    _tr_depth: int
    _cells: list[str]
    _current_cell: str
    _row_cancelled: bool

    def __init__(self) -> None:
        super().__init__()
        self._in_td = False
        self._td_depth = 0
        self._tr_depth = 0
        self._reset_row()

    def _reset_row(self) -> None:
        self._cells = []
        self._current_cell = ""
        self._row_cancelled = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "tr":
            self._start_row()
        elif tag == "td":
            self._start_cell()
        elif tag == "strike" or self._is_cancelled_img(tag, attrs):
            self._row_cancelled = True

    def _start_row(self) -> None:
        if self._tr_depth and not self._in_td and self._td_depth == 0:
            self._finalize_row()
            self._tr_depth = 0
        if self._tr_depth == 0:
            self._reset_row()
        self._tr_depth += 1

    def _start_cell(self) -> None:
        if self._td_depth == 0:
            self._in_td = True
            self._current_cell = ""
        self._td_depth += 1

    @staticmethod
    def _is_cancelled_img(tag: str, attrs: list[tuple[str, str | None]]) -> bool:
        return tag == "img" and any(
            name == "title" and value == "Spiel abgesagt" for name, value in attrs
        )

    def handle_endtag(self, tag: str) -> None:
        if tag == "td":
            self._td_depth = max(0, self._td_depth - 1)
            if self._td_depth == 0:
                self._cells.append(normalize_whitespace(self._current_cell))
                self._in_td = False
        elif tag == "tr":
            self._tr_depth = max(0, self._tr_depth - 1)
            if self._tr_depth == 0:
                self._finalize_row()
                self._reset_row()

    def handle_data(self, data: str) -> None:
        if self._in_td:
            self._current_cell += data

    def _finalize_row(self) -> None:
        raise NotImplementedError


class _HTMLResultsParser(DBBRowParser):
    """Parse basketball-bund.net HTML results tables."""

    def __init__(self) -> None:
        super().__init__()
        self.games: list[Game] = []

    def _finalize_row(self) -> None:
        """Parse completed row into Game if valid."""
        if len(self._cells) < 6 or self._row_cancelled:
            return
        score_str = self._cells[5]
        if not score_str:
            return
        h_score, a_score = parse_score(score_str)
        if h_score is None or a_score is None:
            return
        date = parse_date(self._cells[2])
        if not date:
            return
        nr_text = self._cells[0]
        self.games.append(
            Game(
                date=date,
                home=self._cells[3],
                away=self._cells[4],
                home_score=h_score,
                away_score=a_score,
                nr=int(nr_text) if nr_text.isdigit() else None,
                forfeit=is_forfeit_score(h_score, a_score),
            )
        )


def extract_league_info(html: str) -> LeagueInfo:
    """Extract league metadata from DBB HTML content.

    Parses the league name from the title pattern and the Liganr.
    from the parenthetical section.

    Args:
        html: Raw HTML content.

    Returns:
        LeagueInfo with name and optional number.
    """
    m = _TITLE_RE.search(html)
    name = m.group(1).strip() if m else _LEAGUE_FALLBACK
    nr_match = _LIGANR_RE.search(html)
    number = int(nr_match.group(1)) if nr_match else None
    return LeagueInfo(name=name, number=number)


def read_games(filepath: str) -> tuple[list[Game], LeagueInfo]:
    """Read all valid games from HTML results file.

    Skips struck-through and incomplete rows.

    Args:
        filepath: Path to HTML results file.

    Returns:
        Tuple of (games sorted newest-first, league_info).
    """
    content = read_file_safe(filepath)
    league_info = extract_league_info(content)
    parser = _HTMLResultsParser()
    parser.feed(content)
    parser.games.sort(key=lambda g: g.date, reverse=True)
    return parser.games, league_info


def print_header(
    subtitle: str,
    league_name: str = _LEAGUE_FALLBACK,
    width: int = 70,
) -> None:
    """Print a unified section header.

    Args:
        subtitle: Section subtitle to display.
        league_name: League name to include in header.
        width: Minimum header width in characters.
    """
    title = f"{subtitle} — {league_name}"
    w = max(width, len(title) + 4)
    print(f"\n{'=' * w}")
    print(f"  {title}")
    print(f"{'=' * w}\n")
