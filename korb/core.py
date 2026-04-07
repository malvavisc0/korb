"""Shared models and utilities for DBB (Deutscher Basketball Bund) analysis.

Provides common types, HTML parsing, and date helpers used across modules.
Target: DBB Version ≤11.50.0-623b018 (legacy JSP platform).
"""

import re
import sys
from dataclasses import dataclass
from datetime import datetime
from html.parser import HTMLParser
from typing import Final, Optional

DATE_FMT: Final[str] = "%d.%m.%Y %H:%M"
_LEAGUE_FALLBACK: Final[str] = "Basketball League"

# Regex for league name in DBB HTML titles like:
# "Ergebnisse - MFR U12 mix Bezirksliga Nord (U12 ...)"
# "Spielplan - MFR U12 mix Bezirksliga Nord (U12 ...)"
_TITLE_RE = re.compile(r"(?:Ergebnisse|Spielplan)\s*-\s*(.+?)\s*\(")


@dataclass
class Game:
    """A single completed basketball game."""

    date: datetime
    home: str
    away: str
    home_score: int
    away_score: int


def parse_date(date_str: str) -> Optional[datetime]:
    """Parse date string in format 'DD.MM.YYYY HH:MM'.

    Args:
        date_str: Date string to parse.

    Returns:
        Parsed datetime or None if invalid format.
    """
    try:
        return datetime.strptime(date_str.strip(), DATE_FMT)
    except (ValueError, AttributeError):
        return None


def parse_score(score_str: str) -> tuple[Optional[int], Optional[int]]:
    """Parse score string in format '79 : 75'.

    Args:
        score_str: Score string to parse.

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


class _HTMLResultsParser(HTMLParser):
    """Parse basketball-bund.net HTML results tables."""

    def __init__(self) -> None:
        super().__init__()
        self.games: list[Game] = []
        self._in_td = False
        self._td_depth = 0
        self._cells: list[str] = []
        self._current_cell = ""
        self._row_cancelled = False

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, Optional[str]]]
    ) -> None:  # noqa: unused
        if tag == "td":
            if self._td_depth == 0:
                self._in_td = True
                self._current_cell = ""
            self._td_depth += 1
        elif tag == "strike":
            self._row_cancelled = True

    def handle_endtag(self, tag: str) -> None:
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
        if self._in_td and self._td_depth == 1:
            self._current_cell += data

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
        self.games.append(
            Game(
                date=date,
                home=self._cells[3],
                away=self._cells[4],
                home_score=h_score,
                away_score=a_score,
            )
        )


def extract_league_name(html: str) -> str:
    """Extract league name from DBB HTML title tag.

    Args:
        html: Raw HTML content.

    Returns:
        League name string, or fallback if not found.
    """
    m = _TITLE_RE.search(html)
    return m.group(1).strip() if m else _LEAGUE_FALLBACK


def read_games(filepath: str) -> tuple[list[Game], str]:
    """Read all valid games from HTML results file.

    Skips forfeited games (struck-through rows) and incomplete rows.

    Args:
        filepath: Path to HTML results file.

    Returns:
        Tuple of (games sorted newest-first, league_name).
    """
    content = read_file_safe(filepath)
    league_name = extract_league_name(content)
    parser = _HTMLResultsParser()
    parser.feed(content)
    parser.games.sort(key=lambda g: g.date, reverse=True)
    return parser.games, league_name


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
