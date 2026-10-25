"""Tests for korb.backtest module."""

from datetime import datetime, timedelta

from korb.backtest import BacktestResult, backtest, print_backtest
from korb.core import DATE_FMT, LOCAL_TZ, Game


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


def _results_html(games: list[Game]) -> str:
    rows = "".join(
        f"<tr><td>{nr}</td><td>1</td>"
        f"<td>{game.date.strftime(DATE_FMT)}</td>"
        f"<td>{game.home}</td><td>{game.away}</td>"
        f"<td>{game.home_score} : {game.away_score}</td></tr>"
        for nr, game in enumerate(games, 1)
    )
    return (
        "<html><head><title>Ergebnisse - Test (x; Liganr.: 99999)</title></head>"
        f"<body><table>{rows}</table></body></html>"
    )


class TestBacktest:
    def test_backtest_metrics(self, tmp_path):
        base = datetime(2026, 1, 1, 10, 0, tzinfo=LOCAL_TZ)
        games = [
            Game(
                date=base + timedelta(days=index),
                home="Team A" if index % 2 == 0 else "Team B",
                away="Team B" if index % 2 == 0 else "Team A",
                home_score=80,
                away_score=70,
            )
            for index in range(10)
        ]
        path = tmp_path / "ergebnisse.html"
        path.write_text(_results_html(games))

        result, info = backtest(str(path), min_train_games=5)
        assert info.number == 99999
        assert result.games > 0
        assert 0.0 <= result.winner_accuracy <= 1.0
        assert result.brier >= 0.0
        assert result.score_mae >= 0.0
        assert result.score_rmse >= result.score_mae

    def test_backtest_counts_away_wins(self, tmp_path):
        base = datetime(2026, 1, 1, 10, 0, tzinfo=LOCAL_TZ)
        games = [
            Game(
                date=base + timedelta(days=index),
                home="Team A",
                away="Team B",
                home_score=70,
                away_score=80,
            )
            for index in range(7)
        ]
        path = tmp_path / "ergebnisse.html"
        path.write_text(_results_html(games))

        result, _ = backtest(str(path), min_train_games=5)
        assert result.games == 2
        assert result.winner_games == 2
        assert 0.0 <= result.winner_accuracy <= 1.0

    def test_backtest_insufficient_games(self, tmp_path):
        path = tmp_path / "ergebnisse.html"
        path.write_text(_results_html([_make_game("Team A", "Team B", 80, 70)]))
        result, _ = backtest(str(path), min_train_games=5)
        assert result.games == 0

    def test_backtest_skips_games_with_unrated_teams(self, tmp_path):
        games = [
            _make_game("Team A", "Team B", 80, 70, days_ago=days)
            for days in range(5, 0, -1)
        ]
        games.append(_make_game("Team A", "Newcomer", 75, 70, days_ago=0))
        path = tmp_path / "ergebnisse.html"
        path.write_text(_results_html(games))
        result, _ = backtest(str(path), min_train_games=5)
        assert result.games == 0

    def test_backtest_excludes_draws_from_winner_metrics(self, tmp_path):
        games = [
            _make_game("Team A", "Team B", 80, 70, days_ago=days)
            for days in range(7, 1, -1)
        ]
        games.append(_make_game("Team A", "Team B", 75, 75, days_ago=0))
        path = tmp_path / "ergebnisse.html"
        path.write_text(_results_html(games))
        result, _ = backtest(str(path), min_train_games=5)
        assert result.games == 2
        assert result.winner_games == 1

    def test_print_backtest_empty_message(self, capsys):
        print_backtest(BacktestResult(0, 0, 0.0, 0.0, 0.0, 0.0))
        assert "Not enough completed games" in capsys.readouterr().out
