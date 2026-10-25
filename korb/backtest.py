"""Chronological backtesting for the prediction model."""

from dataclasses import dataclass
from math import sqrt

from korb.core import Game, LeagueInfo, read_games
from korb.model import (
    FATIGUE_THRESHOLD_H,
    Winner,
    fatigue,
    fit_model,
    game_times,
    predict_game,
)

DEFAULT_MIN_TRAIN = 5


@dataclass(frozen=True)
class BacktestResult:
    """Chronological holdout metrics for the prediction model."""

    games: int
    winner_games: int
    winner_accuracy: float
    brier: float
    score_mae: float
    score_rmse: float

    def to_dict(self) -> dict[str, object]:
        """Serializable metrics."""
        return {
            "games": self.games,
            "winner_games": self.winner_games,
            "winner_accuracy": round(self.winner_accuracy, 4),
            "brier": round(self.brier, 4),
            "score_mae": round(self.score_mae, 2),
            "score_rmse": round(self.score_rmse, 2),
        }


def _actual_home_win(game: Game) -> float | None:
    if game.home_score > game.away_score:
        return 1.0
    if game.home_score < game.away_score:
        return 0.0
    return None


def _predict_historical(
    game: Game, prior: list[Game]
) -> tuple[Winner, int, int, float] | None:
    model = fit_model(prior)
    if game.home not in model.ratings or game.away not in model.ratings:
        return None
    times = game_times(prior)
    timestamp = game.date.timestamp()
    threshold_s = FATIGUE_THRESHOLD_H * 3600
    return predict_game(
        game.home,
        game.away,
        model.ratings,
        model.league_avg,
        home_fatigue=fatigue(game.home, timestamp, times, threshold_s),
        away_fatigue=fatigue(game.away, timestamp, times, threshold_s),
        home_advantage=model.home_advantage,
        sigma=model.sigma,
    )


def backtest(
    results_path: str,
    min_train_games: int = DEFAULT_MIN_TRAIN,
) -> tuple[BacktestResult, LeagueInfo]:
    """Evaluate the model chronologically on completed games."""
    games, league_info = read_games(results_path)
    games = sorted(
        (game for game in games if not game.forfeit),
        key=lambda game: game.date,
    )

    evaluated = 0
    winner_games = 0
    correct = 0
    brier = 0.0
    absolute_errors: list[float] = []
    squared_errors: list[float] = []

    for index, game in enumerate(games):
        prior = games[:index]
        if len(prior) < min_train_games:
            continue
        prediction = _predict_historical(game, prior)
        if prediction is None:
            continue
        winner, home_score, away_score, home_probability = prediction

        evaluated += 1
        absolute_errors.extend(
            [
                abs(home_score - game.home_score),
                abs(away_score - game.away_score),
            ]
        )
        squared_errors.extend(
            [
                float((home_score - game.home_score) ** 2),
                float((away_score - game.away_score) ** 2),
            ]
        )

        actual_home = _actual_home_win(game)
        if actual_home is not None:
            winner_games += 1
            correct += int((winner == "home") == (actual_home == 1.0))
            brier += (home_probability - actual_home) ** 2

    if not evaluated:
        return BacktestResult(0, 0, 0.0, 0.0, 0.0, 0.0), league_info

    return (
        BacktestResult(
            games=evaluated,
            winner_games=winner_games,
            winner_accuracy=correct / winner_games if winner_games else 0.0,
            brier=brier / winner_games if winner_games else 0.0,
            score_mae=sum(absolute_errors) / len(absolute_errors),
            score_rmse=sqrt(sum(squared_errors) / len(squared_errors)),
        ),
        league_info,
    )


def print_backtest(result: BacktestResult) -> None:
    """Print backtest metrics."""
    print("\n" + "=" * 70)
    print("  Prediction Backtest")
    print("=" * 70)

    if result.games == 0:
        print("  Not enough completed games to backtest.")
        return

    print(f"  Games evaluated: {result.games}")
    print(
        f"  Winner accuracy: {result.winner_accuracy:.1%} ({result.winner_games} games)"
    )
    print(f"  Brier score: {result.brier:.4f}")
    print(f"  Score MAE: {result.score_mae:.2f}")
    print(f"  Score RMSE: {result.score_rmse:.2f}")
