"""Tests for korb.standings module."""

from collections import defaultdict
from datetime import datetime

from korb.core import Game
from korb.standings import TeamStats, _update_stats


class TestTeamStatsDiff:
    def test_positive(self):
        s = TeamStats(gp=1, pf=80, pa=70)
        assert s.diff == 10

    def test_negative(self):
        s = TeamStats(gp=1, pf=60, pa=75)
        assert s.diff == -15

    def test_zero(self):
        s = TeamStats(gp=1, pf=70, pa=70)
        assert s.diff == 0


class TestTeamStatsPts:
    def test_win_only(self):
        s = TeamStats(w=3)
        assert s.pts == 6

    def test_draw_only(self):
        s = TeamStats(d=2)
        assert s.pts == 2

    def test_loss_only(self):
        s = TeamStats(l=4)
        assert s.pts == 0

    def test_mixed_record(self):
        s = TeamStats(w=5, l=3, d=2)
        assert s.pts == 12  # 5*2 + 3*0 + 2*1


class TestTeamStatsAvg:
    def test_zero_games(self):
        s = TeamStats()
        assert s.avg_pf == 0.0
        assert s.avg_pa == 0.0

    def test_normal_case(self):
        s = TeamStats(gp=4, pf=320, pa=280)
        assert s.avg_pf == 80.0
        assert s.avg_pa == 70.0


class TestUpdateStats:
    def _game(self, home_score: int, away_score: int) -> Game:
        return Game(
            date=datetime(2026, 1, 15, 10, 0),
            home="Team A",
            away="Team B",
            home_score=home_score,
            away_score=away_score,
        )

    def test_home_win(self):
        teams = defaultdict(TeamStats)
        _update_stats(teams, self._game(80, 70))
        assert teams["Team A"].w == 1
        assert teams["Team A"].l == 0
        assert teams["Team B"].l == 1
        assert teams["Team B"].w == 0

    def test_away_win(self):
        teams = defaultdict(TeamStats)
        _update_stats(teams, self._game(60, 75))
        assert teams["Team A"].l == 1
        assert teams["Team B"].w == 1

    def test_draw(self):
        teams = defaultdict(TeamStats)
        _update_stats(teams, self._game(70, 70))
        assert teams["Team A"].d == 1
        assert teams["Team B"].d == 1

    def test_points_for_against(self):
        teams = defaultdict(TeamStats)
        _update_stats(teams, self._game(80, 65))
        assert teams["Team A"].pf == 80
        assert teams["Team A"].pa == 65
        assert teams["Team B"].pf == 65
        assert teams["Team B"].pa == 80


class TestCalculateStandings:
    def test_sorting(self, ergebnisse_path):
        from korb.standings import calculate_standings

        standings, _ = calculate_standings(ergebnisse_path)
        for i in range(len(standings) - 1):
            s1, s2 = standings[i], standings[i + 1]
            assert (s1.stats.pts, s1.stats.diff, s1.stats.pf) >= (
                s2.stats.pts,
                s2.stats.diff,
                s2.stats.pf,
            )

    def test_empty_input(self, tmp_path):
        from korb.standings import calculate_standings

        f = tmp_path / "empty.html"
        f.write_text(
            "<html><head>"
            "<title>Ergebnisse - League (x)</title>"
            "</head><body></body></html>"
        )
        standings, league_info = calculate_standings(str(f))
        assert league_info.name == "League"
        assert league_info.number is None
        assert standings == []

    def test_returns_league_info(self, ergebnisse_path):
        from korb.standings import calculate_standings

        standings, league_info = calculate_standings(ergebnisse_path)
        assert league_info.name == "Test Bezirksliga"
        assert league_info.number == 99999
