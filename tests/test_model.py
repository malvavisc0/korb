"""Tests for korb.model module."""

from datetime import datetime, timedelta

import pytest

from korb.core import LOCAL_TZ, Game, read_games
from korb.model import (
    MAX_PROBABILITY,
    MIN_SIGMA,
    Prediction,
    TeamRating,
    _recency_weight,
    _solve,
    fatigue,
    fit_strength,
    game_times,
    predict_game,
)
from korb.schedule import ScheduledGame


def _make_game(
    home: str,
    away: str,
    home_score: int,
    away_score: int,
    days_ago: int = 0,
) -> Game:
    dt = datetime(2026, 1, 15, 10, 0, tzinfo=LOCAL_TZ) - timedelta(days=days_ago)
    return Game(
        date=dt, home=home, away=away, home_score=home_score, away_score=away_score
    )


class TestRecencyWeight:
    def test_recent_game(self):
        game = _make_game("A", "B", 80, 70, days_ago=0)
        assert _recency_weight(game, game.date.timestamp()) == 1.0

    def test_old_game(self):
        game = _make_game("A", "B", 80, 70, days_ago=180)
        reference = (game.date + timedelta(days=180)).timestamp()
        weight = _recency_weight(game, reference)
        assert 0.0 < weight < 0.5


class TestStrengthModel:
    def test_empty_games(self):
        teams, model = fit_strength([])
        assert teams == {}
        assert model.ratings == {}
        assert model.league_avg == 50.0

    def test_normal_case(self, ergebnisse_path):
        teams, model = fit_strength(read_games(ergebnisse_path)[0])
        assert teams
        assert model.ratings
        assert model.league_avg > 0
        assert model.sigma >= MIN_SIGMA
        for rating in model.ratings.values():
            assert rating.offense > 0
            assert rating.defense > 0

    def test_stronger_team_gets_better_ratings(self):
        games = [
            _make_game("Strong", "Weak", 100, 50, days_ago=2),
            _make_game("Strong", "Weak", 100, 60, days_ago=1),
            _make_game("Weak", "Strong", 55, 95, days_ago=0),
        ]
        _teams, model = fit_strength(games)
        assert model.ratings["Strong"].offense > model.ratings["Weak"].offense
        assert model.ratings["Strong"].defense < model.ratings["Weak"].defense

    def test_forfeits_do_not_affect_ratings(self):
        normal = _make_game("Team A", "Team B", 80, 70)
        forfeit = Game(
            date=normal.date,
            home="Team A",
            away="Team C",
            home_score=20,
            away_score=0,
            nr=2,
            forfeit=True,
        )
        _teams, model = fit_strength([normal, forfeit])
        _teams_only, model_only = fit_strength([normal])
        assert model.ratings == model_only.ratings
        assert model.league_avg == model_only.league_avg

    def test_only_forfeits_returns_neutral_model(self):
        forfeit = Game(
            date=datetime(2026, 1, 15, 10, 0, tzinfo=LOCAL_TZ),
            home="Team A",
            away="Team B",
            home_score=20,
            away_score=0,
            forfeit=True,
        )
        teams, model = fit_strength([forfeit])
        assert teams
        assert model.ratings == {}
        assert model.league_avg == 50.0


class TestPredictGame:
    def test_home_win(self):
        ratings = {
            "A": TeamRating(1.2, 0.9),
            "B": TeamRating(0.8, 1.1),
        }
        winner, hs, as_, probability = predict_game("A", "B", ratings, 75.0)
        assert winner == "home"
        assert hs > as_
        assert 0.0 <= probability <= 1.0

    def test_away_win(self):
        ratings = {
            "A": TeamRating(0.8, 1.2),
            "B": TeamRating(1.3, 0.8),
        }
        winner, hs, as_, probability = predict_game("A", "B", ratings, 75.0)
        assert winner == "away"
        assert as_ > hs
        assert 0.0 <= probability <= 1.0

    def test_extreme_margin_probability_is_clamped(self):
        ratings = {"A": TeamRating(2.0, 0.5), "B": TeamRating(0.5, 2.0)}
        _winner, _hs, _as_, probability = predict_game("A", "B", ratings, 75.0)
        assert probability == MAX_PROBABILITY

    def test_tie_break(self):
        ratings = {"A": TeamRating(1.0, 1.0), "B": TeamRating(1.0, 1.0)}
        winner, hs, as_, _probability = predict_game("A", "B", ratings, 75.0)
        assert hs != as_
        assert winner == "home"

    def test_fatigue_effect(self):
        ratings = {"A": TeamRating(1.2, 0.9), "B": TeamRating(1.0, 1.0)}
        _, hs_normal, _as_normal, _p = predict_game("A", "B", ratings, 75.0)
        _, hs_fatigued, _as, _p = predict_game(
            "A",
            "B",
            ratings,
            75.0,
            home_fatigue=0.95,
        )
        assert hs_fatigued < hs_normal

    def test_unknown_team_uses_neutral_rating(self):
        winner, hs, as_, probability = predict_game("A", "B", {}, 75.0)
        assert winner in ("home", "away")
        assert hs >= 0
        assert as_ >= 0
        assert 0.0 <= probability <= 1.0


class TestFatigue:
    def test_prior_game_within_threshold(self):
        base = datetime(2026, 1, 15, 10, 0, tzinfo=LOCAL_TZ)
        times = {"Team A": [(base - timedelta(hours=24)).timestamp()]}
        assert fatigue("Team A", base.timestamp(), times, 36 * 3600) == 0.95

    def test_prior_game_outside_threshold(self):
        base = datetime(2026, 1, 15, 10, 0, tzinfo=LOCAL_TZ)
        times = {"Team A": [(base - timedelta(hours=48)).timestamp()]}
        assert fatigue("Team A", base.timestamp(), times, 36 * 3600) == 1.0

    def test_later_game_does_not_cause_fatigue(self):
        base = datetime(2026, 1, 15, 10, 0, tzinfo=LOCAL_TZ)
        times = {"Team A": [(base + timedelta(hours=24)).timestamp()]}
        assert fatigue("Team A", base.timestamp(), times, 36 * 3600) == 1.0

    def test_forfeits_are_ignored(self):
        game = Game(
            date=datetime(2026, 1, 15, 10, 0, tzinfo=LOCAL_TZ),
            home="Team A",
            away="Team B",
            home_score=20,
            away_score=0,
            forfeit=True,
        )
        assert game_times([game]) == {}


def _scheduled_game(nr: int = 1) -> ScheduledGame:
    return ScheduledGame(
        nr=nr,
        day=1,
        date=datetime(2026, 1, 15, 10, 0, tzinfo=LOCAL_TZ),
        home="Team A",
        away="Team B",
        venue="Halle",
        cancelled=False,
    )


class TestPrediction:
    def test_win_probability_home(self):
        prediction = Prediction(_scheduled_game(), "home", 80, 70, 0.8)
        assert prediction.win_probability == 0.8

    def test_win_probability_away(self):
        prediction = Prediction(_scheduled_game(), "away", 70, 80, 0.3)
        assert prediction.win_probability == 0.7


class TestSolve:
    def test_singular_matrix_raises(self):
        with pytest.raises(ValueError):
            _solve([[0.0]], [1.0])
