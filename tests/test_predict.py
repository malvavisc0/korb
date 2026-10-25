"""Tests for korb.predict module."""

from datetime import datetime

import pytest

from korb.core import LOCAL_TZ, Game
from korb.model import Prediction
from korb.predict import (
    PredictionError,
    _pending_games,
    format_prediction,
    predict_standings,
    print_predicted_standings,
    print_predictions,
)
from korb.schedule import ScheduledGame, parse_schedule


class TestPredictStandings:
    def test_full_integration(self, ergebnisse_path, spielplan_path):
        standings, predictions, league_info = predict_standings(
            ergebnisse_path, spielplan_path
        )
        assert standings
        assert predictions
        assert league_info.name == "Test Bezirksliga"
        assert league_info.number == 99999
        assert all(0.0 <= pred.win_probability <= 1.0 for pred in predictions)

    def test_no_pending_games(self, ergebnisse_path, spielplan_finalized_path):
        standings, predictions, _ = predict_standings(
            ergebnisse_path, spielplan_finalized_path
        )
        assert predictions == []
        assert standings


class TestPendingGames:
    def test_past_unplayed_game_is_pending(self, tmp_path):
        path = tmp_path / "spielplan.html"
        path.write_text(
            "<html><head><title>Spielplan - Test (x)</title></head><body>"
            "<table><tr><td>1</td><td>1</td><td>01.01.2020 10:00</td>"
            "<td>Team A</td><td>Team B</td><td>Halle</td></tr></table>"
            "</body></html>"
        )
        schedule, _ = parse_schedule(str(path))
        assert len(_pending_games(schedule, [])) == 1

    def test_played_fixture_excluded_by_number(self, tmp_path):
        path = tmp_path / "spielplan.html"
        path.write_text(
            "<html><head><title>Spielplan - Test (x)</title></head><body>"
            "<table><tr><td>1</td><td>1</td><td>20.01.2026 10:00</td>"
            "<td>Team A</td><td>Team B</td><td>Halle</td></tr></table>"
            "</body></html>"
        )
        played = [
            Game(
                nr=1,
                date=datetime(2025, 12, 20, 10, 0, tzinfo=LOCAL_TZ),
                home="Team A",
                away="Team B",
                home_score=80,
                away_score=70,
            )
        ]
        schedule, _ = parse_schedule(str(path))
        assert _pending_games(schedule, played) == []


class TestLeagueValidation:
    def test_mismatched_league_numbers_raise(self, ergebnisse_path, tmp_path):
        schedule = tmp_path / "spielplan.html"
        schedule.write_text(
            "<html><head><title>Spielplan - Other (x; Liganr.: 11111)</title></head>"
            "<body><table><tr><td>1</td><td>1</td><td>01.06.2026 10:00</td>"
            "<td>Team Alpha</td><td>Team Beta</td><td>Halle</td></tr></table>"
            "</body></html>"
        )
        with pytest.raises(PredictionError):
            predict_standings(ergebnisse_path, str(schedule))


class TestPredictionOutput:
    def test_format_prediction(self):
        game = ScheduledGame(
            nr=7,
            day=2,
            date=datetime(2026, 1, 15, 10, 0, tzinfo=LOCAL_TZ),
            home="Team A",
            away="Team B",
            venue="Halle",
            cancelled=False,
        )
        prediction = Prediction(game, "home", 80, 70, 0.75)
        payload = format_prediction(prediction)
        assert payload["winner"] == "home"
        assert payload["win_probability"] == 0.75
        assert payload["date"] == "15.01.2026 10:00"

    def test_print_predictions(self, capsys):
        game = ScheduledGame(
            nr=1,
            day=1,
            date=datetime(2026, 1, 15, 10, 0, tzinfo=LOCAL_TZ),
            home="Team A",
            away="Team B",
            venue="Halle",
            cancelled=False,
        )
        print_predictions([Prediction(game, "home", 80, 70, 0.75)])
        output = capsys.readouterr().out
        assert "Team A" in output
        assert "75%" in output

    def test_print_predictions_empty(self, capsys):
        print_predictions([])
        assert "No pending games" in capsys.readouterr().out

    def test_print_predicted_standings_empty(self, capsys):
        print_predicted_standings([])
        assert "No predictions" in capsys.readouterr().out
