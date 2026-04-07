"""Tests for korb.predict module."""

from datetime import datetime, timedelta

from korb.core import Game
from korb.predict import (
    _build_ratings,
    _calc_form_totals,
    _recency_weight,
    calc_strength,
    predict_game,
)
from korb.standings import TeamStats


def _make_game(
    home: str, away: str,
    home_score: int, away_score: int,
    days_ago: int = 0,
) -> Game:
    dt = datetime(2026, 1, 15, 10, 0) - timedelta(days=days_ago)
    return Game(date=dt, home=home, away=away,
                home_score=home_score, away_score=away_score)


class TestRecencyWeight:
    def test_recent_game(self):
        game = _make_game("A", "B", 80, 70, days_ago=0)
        ref = game.date.timestamp()
        w = _recency_weight(game, ref)
        assert w == 1.0

    def test_old_game(self):
        game = _make_game("A", "B", 80, 70, days_ago=180)
        ref = datetime(2026, 1, 15, 10, 0).timestamp()
        w = _recency_weight(game, ref)
        assert 0.0 < w < 0.5

    def test_zero_days(self):
        game = _make_game("A", "B", 80, 70, days_ago=0)
        ref = game.date.timestamp()
        w = _recency_weight(game, ref)
        assert w == 1.0


class TestCalcStrength:
    def test_empty_games(self, tmp_path):
        f = tmp_path / "empty.html"
        f.write_text(
            "<html><head>"
            "<title>Ergebnisse - L (x)</title>"
            "</head><body></body></html>"
        )
        teams, ratings, avg = calc_strength(str(f))
        assert teams == {}
        assert ratings == {}
        assert avg == 50.0

    def test_normal_case(self, ergebnisse_path):
        teams, ratings, avg = calc_strength(ergebnisse_path)
        assert len(teams) > 0
        assert len(ratings) > 0
        assert avg > 0
        for name, (off, def_) in ratings.items():
            assert off > 0
            assert def_ > 0


class TestCalcFormTotals:
    def test_last_n_games_only(self):
        games = [
            _make_game("A", "B", 80, 70, days_ago=i)
            for i in range(10)
        ]
        fpf, fpa, fgp = _calc_form_totals(games)
        # Each team appears in 10 games, but only last 5 counted
        assert fgp["A"] == 5
        assert fgp["B"] == 5

    def test_team_tracking(self):
        games = [
            _make_game("A", "B", 80, 70, days_ago=0),
            _make_game("C", "D", 60, 65, days_ago=1),
        ]
        fpf, fpa, fgp = _calc_form_totals(games)
        assert "A" in fpf
        assert "B" in fpf
        assert "C" in fpf
        assert "D" in fpf


class TestBuildRatings:
    def test_min_games_blend(self):
        # Team with 1 game should be blended toward 1.0
        w_pf = {"A": 80.0}
        w_pa = {"A": 70.0}
        w_gp = {"A": 1.0}
        league_avg = 75.0
        teams = {"A": TeamStats(gp=1, pf=80, pa=70)}
        form_pf, form_pa, form_gp = {}, {}, {}

        ratings = _build_ratings(w_pf, w_pa, w_gp, league_avg, teams,
                                 form_pf, form_pa, form_gp)
        off, def_ = ratings["A"]
        # With 1 game and MIN_GAMES=3, blend = 1/3
        raw_off = (80.0 / 1.0) / 75.0  # ~1.067
        expected_off = (1 / 3) * raw_off + (2 / 3) * 1.0
        assert abs(off - expected_off) < 0.001

    def test_form_blend(self):
        # Team with enough games should get form blended in
        w_pf = {"A": 400.0}
        w_pa = {"A": 350.0}
        w_gp = {"A": 5.0}
        league_avg = 75.0
        teams = {"A": TeamStats(gp=5, pf=400, pa=350)}
        # Form: last 5 games with different avg
        form_pf = {"A": 500.0}
        form_pa = {"A": 300.0}
        form_gp = {"A": 5}

        ratings = _build_ratings(w_pf, w_pa, w_gp, league_avg, teams,
                                 form_pf, form_pa, form_gp)
        off, def_ = ratings["A"]
        # Should be a blend of season and form
        assert off > 0
        assert def_ > 0


class TestPredictGame:
    def test_home_win(self):
        ratings = {"A": (1.2, 0.9), "B": (0.8, 1.1)}
        winner, hs, as_ = predict_game("A", "B", ratings, 75.0)
        assert winner == "home"
        assert hs > as_

    def test_away_win(self):
        ratings = {"A": (0.8, 1.2), "B": (1.3, 0.8)}
        winner, hs, as_ = predict_game("A", "B", ratings, 75.0)
        assert winner == "away"
        assert as_ > hs

    def test_tie_break(self):
        # Equal ratings → home advantage should break tie
        ratings = {"A": (1.0, 1.0), "B": (1.0, 1.0)}
        winner, hs, as_ = predict_game("A", "B", ratings, 75.0)
        assert hs != as_  # No tie in basketball
        assert winner == "home"  # Home advantage tiebreak

    def test_fatigue_effect(self):
        ratings = {"A": (1.2, 0.9), "B": (1.0, 1.0)}
        _, hs_normal, as_normal = predict_game("A", "B", ratings, 75.0)
        _, hs_fatigued, _ = predict_game(
            "A", "B", ratings, 75.0, home_fatigue=0.95,
        )
        assert hs_fatigued < hs_normal  # Fatigued home scores less


class TestPredictStandings:
    def test_full_integration(self, ergebnisse_path, spielplan_path):
        from korb.predict import predict_standings
        standings, preds = predict_standings(ergebnisse_path, spielplan_path)
        assert len(standings) > 0
        # Verify sorting
        for i in range(len(standings) - 1):
            s1, s2 = standings[i], standings[i + 1]
            assert (s1.stats.pts, s1.stats.diff, s1.stats.pf) >= (
                s2.stats.pts, s2.stats.diff, s2.stats.pf,
            )

    def test_no_pending_games(self, ergebnisse_path, spielplan_finalized_path):
        from korb.predict import predict_standings
        standings, preds = predict_standings(
            ergebnisse_path, spielplan_finalized_path
        )
        assert len(preds) == 0
        # Standings should still reflect completed games
        assert len(standings) > 0
