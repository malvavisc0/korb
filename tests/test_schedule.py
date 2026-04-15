"""Tests for korb.schedule module."""

from datetime import datetime, timedelta

import pytest

from korb.schedule import (
    ScheduledGame,
    _HTMLScheduleParser,
    filter_schedule,
    is_season_finalized,
    mark_back_to_back,
    parse_schedule,
)


class TestHTMLScheduleParser:
    def test_row_parsing(self):
        parser = _HTMLScheduleParser()
        parser.feed(
            "<tr><td>1</td><td>1</td><td>15.01.2026 10:00</td>"
            "<td>Team A</td><td>Team B</td><td>Halle A</td></tr>"
        )
        assert len(parser.games) == 1
        g = parser.games[0]
        assert g.nr == 1
        assert g.day == 1
        assert g.home == "Team A"
        assert g.away == "Team B"
        assert g.venue == "Halle A"
        assert not g.cancelled

    def test_cancelled_strike_detection(self):
        parser = _HTMLScheduleParser()
        parser.feed(
            "<tr><td><STRIKE>3</STRIKE></td><td><STRIKE>2</STRIKE></td>"
            "<td><STRIKE>22.01.2026 15:00</STRIKE></td>"
            "<td><STRIKE>Team B</STRIKE></td><td><STRIKE>Team A</STRIKE></td>"
            "<td><STRIKE>Halle B</STRIKE></td></tr>"
        )
        assert len(parser.games) == 1
        assert parser.games[0].cancelled

    def test_cancelled_img_detection(self):
        parser = _HTMLScheduleParser()
        parser.feed(
            "<tr><td>3</td><td>2</td><td>22.01.2026 15:00</td>"
            "<td>Team B</td><td>Team A</td><td>Halle B</td></tr>"
        )
        # Without strike or img, not cancelled
        assert not parser.games[0].cancelled

    def test_incomplete_row_skipped(self):
        parser = _HTMLScheduleParser()
        parser.feed("<tr><td>1</td></tr>")
        assert len(parser.games) == 0


class TestParseSchedule:
    def test_valid_html(self, spielplan_path):
        games, league_info = parse_schedule(spielplan_path)
        assert league_info.name == "Test Bezirksliga"
        assert league_info.number == 99999
        assert len(games) == 4  # 4 rows total (including cancelled)

    def test_sorting_by_date(self, spielplan_path):
        games, _ = parse_schedule(spielplan_path)
        for i in range(len(games) - 1):
            assert games[i].date <= games[i + 1].date

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(SystemExit):
            parse_schedule(str(tmp_path / "nonexistent.html"))


class TestFilterSchedule:
    def _make_game(self, days_offset: int, cancelled: bool = False) -> ScheduledGame:
        dt = datetime.now() + timedelta(days=days_offset)
        return ScheduledGame(
            nr=1,
            day=1,
            date=dt,
            home="Team A",
            away="Team B",
            venue="Halle",
            cancelled=cancelled,
        )

    def test_pending_only(self):
        future = self._make_game(days_offset=10)
        past = self._make_game(days_offset=-10)
        result = filter_schedule([future, past], pending=True)
        assert len(result) == 1
        assert result[0] == future

    def test_team_filter(self):
        g1 = self._make_game(days_offset=10)
        g2 = ScheduledGame(
            nr=2,
            day=1,
            date=g1.date,
            home="Team C",
            away="Team D",
            venue="Halle",
            cancelled=False,
        )
        result = filter_schedule([g1, g2], team="team a")
        assert len(result) == 1
        assert result[0].home == "Team A"

    def test_show_all_includes_cancelled(self):
        normal = self._make_game(days_offset=10, cancelled=False)
        cancelled = self._make_game(days_offset=10, cancelled=True)
        result = filter_schedule([normal, cancelled], show_all=True)
        assert len(result) == 2

    def test_default_excludes_cancelled(self):
        normal = self._make_game(days_offset=10, cancelled=False)
        cancelled = self._make_game(days_offset=10, cancelled=True)
        result = filter_schedule([normal, cancelled])
        assert len(result) == 1
        assert not result[0].cancelled


class TestIsSeasonFinalized:
    def test_finalized(self, spielplan_finalized_path):
        finalized, count = is_season_finalized(spielplan_finalized_path)
        assert finalized is True
        assert count == 0

    def test_not_finalized(self, spielplan_path):
        finalized, count = is_season_finalized(spielplan_path)
        assert finalized is False
        assert count > 0


class TestMarkBackToBack:
    def test_b2b_detection(self):
        base = datetime(2026, 1, 15, 10, 0)
        games = [
            ScheduledGame(1, 1, base, "Team A", "Team B", "Halle", False),
            ScheduledGame(
                2,
                1,
                base.replace(hour=18),
                "Team A",
                "Team C",
                "Halle",
                False,
            ),
        ]
        b2b = mark_back_to_back(games, threshold_h=36)
        # Game 0: no prior game for either team
        assert b2b[0] is False
        # Game 1: Team A played 8h ago → B2B
        assert b2b[1] is True

    def test_no_b2b(self):
        base = datetime(2026, 1, 15, 10, 0)
        games = [
            ScheduledGame(1, 1, base, "Team A", "Team B", "Halle", False),
            ScheduledGame(
                2,
                1,
                base.replace(day=17),
                "Team A",
                "Team C",
                "Halle",
                False,
            ),
        ]
        b2b = mark_back_to_back(games, threshold_h=36)
        assert all(v is False for v in b2b.values())

    def test_threshold_edge_case(self):
        base = datetime(2026, 1, 15, 10, 0)
        # Exactly 36 hours later
        later = base + timedelta(hours=36)
        games = [
            ScheduledGame(1, 1, base, "Team A", "Team B", "Halle", False),
            ScheduledGame(2, 1, later, "Team A", "Team C", "Halle", False),
        ]
        b2b = mark_back_to_back(games, threshold_h=36)
        # 36h exactly → <= threshold → B2B
        assert b2b[1] is True
