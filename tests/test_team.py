"""Tests for korb.team module."""

from datetime import datetime

from korb.core import Game
from korb.team import (
    GameResult,
    _game_to_result,
    _result_code,
    _sparkline_char,
    get_team_results,
)


class TestGameResultDiff:
    _DATE = datetime(2026, 1, 15, 10, 0)

    def test_positive(self):
        r = GameResult(self._DATE, "Team B", "Home", 85, 70, "W")
        assert r.diff == 15

    def test_negative(self):
        r = GameResult(self._DATE, "Team B", "Away", 60, 80, "L")
        assert r.diff == -20

    def test_zero(self):
        r = GameResult(self._DATE, "Team B", "Home", 70, 70, "D")
        assert r.diff == 0


class TestResultCode:
    def test_win(self):
        assert _result_code(80, 70) == "W"

    def test_loss(self):
        assert _result_code(60, 75) == "L"

    def test_draw(self):
        assert _result_code(70, 70) == "D"


class TestGameToResult:
    def _game(self, home_score: int, away_score: int) -> Game:
        return Game(
            date=datetime(2026, 1, 15, 10, 0),
            home="Team A",
            away="Team B",
            home_score=home_score,
            away_score=away_score,
        )

    def test_home_perspective_win(self):
        r = _game_to_result(self._game(80, 70), is_home=True)
        assert r.date == datetime(2026, 1, 15, 10, 0)
        assert r.opponent == "Team B"
        assert r.home_away == "Home"
        assert r.our_score == 80
        assert r.opp_score == 70
        assert r.result == "W"

    def test_away_perspective_loss(self):
        r = _game_to_result(self._game(80, 70), is_home=False)
        assert r.date == datetime(2026, 1, 15, 10, 0)
        assert r.opponent == "Team A"
        assert r.home_away == "Away"
        assert r.our_score == 70
        assert r.opp_score == 80
        assert r.result == "L"


class TestGetTeamResults:
    def test_partial_match(self, ergebnisse_path):
        results, _ = get_team_results("Alpha", ergebnisse_path)
        assert len(results) > 0
        # Team Alpha: 3 non-cancelled games (1 cancelled skipped)
        assert len(results) == 3
        opponents = {r.opponent for r in results}
        assert "Team Beta" in opponents
        assert "Team Delta" in opponents

    def test_case_insensitive(self, ergebnisse_path):
        r1, _ = get_team_results("alpha", ergebnisse_path)
        r2, _ = get_team_results("ALPHA", ergebnisse_path)
        assert len(r1) == len(r2)

    def test_no_match(self, ergebnisse_path):
        results, _ = get_team_results("NonExistent", ergebnisse_path)
        assert results == []


class TestSparklineChar:
    def test_win(self):
        assert _sparkline_char("W") == "█"

    def test_loss(self):
        assert _sparkline_char("L") == "▄"

    def test_draw(self):
        assert _sparkline_char("D") == "─"

    def test_unknown(self):
        assert _sparkline_char("X") == " "


class TestGameResultToDict:
    def test_to_dict_includes_date(self):
        date = datetime(2026, 3, 15, 18, 0)
        r = GameResult(date, "Team B", "Home", 79, 75, "W")
        d = r.to_dict()
        assert d["date"] == "15.03.2026 18:00"
        assert d["opponent"] == "Team B"
        assert d["home_away"] == "Home"
        assert d["our_score"] == 79
        assert d["opp_score"] == 75
        assert d["result"] == "W"
        assert d["diff"] == 4
