"""Predict final standings and print remaining-game forecasts.

Target: DBB Version ≤12.01.1-f733da5 (legacy JSP platform).
"""

from bisect import insort
from collections import defaultdict
from dataclasses import replace
from datetime import datetime

from korb.core import DATE_FMT, Game, LeagueInfo, normalize_name, read_games
from korb.model import (
    FATIGUE_THRESHOLD_H,
    Prediction,
    fatigue,
    fit_strength,
    game_times,
    predict_game,
)
from korb.schedule import ScheduledGame, filter_schedule, parse_schedule
from korb.standings import (
    Standing,
    TeamStats,
    print_standings_rows,
    rank_standings,
    record_game,
)


class PredictionError(ValueError):
    """Raised when prediction inputs are inconsistent."""


def _copy_stats(teams_base: dict[str, TeamStats]) -> dict[str, TeamStats]:
    """Deep-copy current team stats into a fresh defaultdict."""
    return defaultdict(
        TeamStats, {name: replace(stats) for name, stats in teams_base.items()}
    )


def _fixture_key(home: str, away: str, date: datetime) -> tuple[str, str, str]:
    return (normalize_name(home), normalize_name(away), date.strftime("%d.%m.%Y"))


def _pending_games(
    schedule: list[ScheduledGame], played: list[Game]
) -> list[ScheduledGame]:
    """Return scheduled games not already present in results."""
    played_numbers = {game.nr for game in played if game.nr is not None}
    played_keys = {_fixture_key(game.home, game.away, game.date) for game in played}
    pending = [
        game
        for game in filter_schedule(schedule)
        if game.nr not in played_numbers
        and _fixture_key(game.home, game.away, game.date) not in played_keys
    ]
    pending.sort(key=lambda game: game.date)
    return pending


def predict_standings(
    results_path: str,
    html_path: str,
) -> tuple[list[Standing], list[Prediction], LeagueInfo]:
    """Predict final standings based on remaining games."""
    played, league_info = read_games(results_path)
    schedule, schedule_info = parse_schedule(html_path)
    if (
        league_info.number is not None
        and schedule_info.number is not None
        and league_info.number != schedule_info.number
    ):
        raise PredictionError(
            "Results and schedule are from different leagues "
            f"({league_info.number} != {schedule_info.number})."
        )

    teams_base, model = fit_strength(played)
    teams = _copy_stats(teams_base)
    pending = _pending_games(schedule, played)

    times = game_times(played)
    threshold_s = FATIGUE_THRESHOLD_H * 3600

    preds: list[Prediction] = []
    for game in pending:
        timestamp = game.date.timestamp()
        home_fatigue = fatigue(game.home, timestamp, times, threshold_s)
        away_fatigue = fatigue(game.away, timestamp, times, threshold_s)

        winner, home_score, away_score, home_probability = predict_game(
            game.home,
            game.away,
            model.ratings,
            model.league_avg,
            home_fatigue=home_fatigue,
            away_fatigue=away_fatigue,
            home_advantage=model.home_advantage,
            sigma=model.sigma,
        )

        insort(times.setdefault(game.home, []), timestamp)
        insort(times.setdefault(game.away, []), timestamp)
        preds.append(
            Prediction(
                game,
                winner,
                home_score,
                away_score,
                home_probability,
            )
        )
        record_game(
            teams,
            game.home,
            game.away,
            home_score,
            away_score,
            forfeit=False,
        )

    standings = [Standing(name, stats) for name, stats in teams.items()]
    rank_games = list(played) + [
        Game(
            nr=pred.game.nr,
            date=pred.game.date,
            home=pred.game.home,
            away=pred.game.away,
            home_score=pred.home_score,
            away_score=pred.away_score,
        )
        for pred in preds
    ]
    return rank_standings(standings, rank_games), preds, league_info


def print_predictions(preds: list[Prediction]) -> None:
    """Print predicted game outcomes."""
    print("\n" + "=" * 70)
    print("  Predicted Remaining Games")
    print("=" * 70)

    if not preds:
        print("  No pending games.")
        return

    hw = max(len(pred.game.home) for pred in preds)
    aw = max(len(pred.game.away) for pred in preds)

    for pred in preds:
        game = pred.game
        date_str = game.date.strftime("%d.%m.%y %H:%M")
        tag = f"<- {game.home}" if pred.winner == "home" else f"-> {game.away}"
        print(
            f"  {date_str}  {game.home:<{hw}}  "
            f"{pred.home_score:>3} : {pred.away_score:<3}  "
            f"{game.away:<{aw}}  {pred.win_probability:>5.0%}  {tag}"
        )


def print_predicted_standings(standings: list[Standing]) -> None:
    """Print predicted final standings."""
    print("\n" + "=" * 70)
    print("  Predicted Final Standings")
    print("=" * 70)

    if not standings:
        print("No predictions.")
        return

    print_standings_rows(standings)
    print()


def format_prediction(pred: Prediction) -> dict[str, object]:
    """Serializable prediction payload."""
    return {
        "nr": pred.game.nr,
        "date": pred.game.date.strftime(DATE_FMT),
        "home": pred.game.home,
        "away": pred.game.away,
        "winner": pred.winner,
        "home_score": pred.home_score,
        "away_score": pred.away_score,
        "win_probability": round(pred.win_probability, 3),
    }
