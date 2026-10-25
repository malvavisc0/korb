"""Opponent-adjusted team strength model for DBB leagues.

Ratings are fitted with weighted ridge regression on point differentials,
which adjusts for opponent strength. Predictions convert the fitted
offensive/defensive ratings into the multiplicative score model and
report home-win probabilities.
Target: DBB Version ≤12.01.1-f733da5 (legacy JSP platform).
"""

from bisect import bisect_left
from collections import defaultdict
from dataclasses import dataclass
from math import erf, exp, sqrt
from typing import Literal

from korb.core import Game
from korb.schedule import ScheduledGame
from korb.standings import TeamStats, record_game

Winner = Literal["home", "away"]

RECENCY_HALF_LIFE = 60.0
RIDGE_LAMBDA = 1.0
HFA_PRIOR_WEIGHT = 5.0
DEFAULT_HOME_ADVANTAGE = 1.03
DEFAULT_SIGMA = 12.0
MIN_SIGMA = 10.0
MIN_PROBABILITY = 0.01
MAX_PROBABILITY = 0.99
FATIGUE_THRESHOLD_H = 36
FATIGUE_PENALTY = 0.95
FORM_GAMES = 5
FORM_WEIGHT = 0.30


@dataclass(frozen=True)
class TeamRating:
    """Opponent-adjusted offensive and defensive ratings."""

    offense: float
    defense: float


@dataclass(frozen=True)
class StrengthModel:
    """Fitted team ratings and global model parameters."""

    ratings: dict[str, TeamRating]
    league_avg: float
    home_advantage: float
    sigma: float


@dataclass(frozen=True)
class Prediction:
    """Predicted outcome for a scheduled game."""

    game: ScheduledGame
    winner: Winner
    home_score: int
    away_score: int
    home_win_probability: float

    @property
    def win_probability(self) -> float:
        """Probability assigned to the predicted winner."""
        if self.winner == "home":
            return self.home_win_probability
        return 1.0 - self.home_win_probability


def _recency_weight(game: Game, ref_ts: float) -> float:
    """Exponential decay weight based on days since game."""
    days_ago = max((ref_ts - game.date.timestamp()) / 86400, 0)
    return exp(-0.693 * days_ago / RECENCY_HALF_LIFE)


def _weighted_league_avg(games: list[Game], weights: list[float]) -> float:
    """Weighted average points per team per game."""
    total_weight = sum(weights) * 2
    total_points = sum(
        weight * (game.home_score + game.away_score)
        for game, weight in zip(games, weights, strict=True)
    )
    return total_points / total_weight


def _add_observation(
    matrix: list[list[float]],
    vector: list[float],
    terms: tuple[tuple[int, float], ...],
    target: float,
    weight: float,
) -> None:
    """Add one weighted least-squares observation to the normal equations."""
    for i, coefficient_i in terms:
        vector[i] += weight * coefficient_i * target
        for j, coefficient_j in terms:
            matrix[i][j] += weight * coefficient_i * coefficient_j


def _build_normal_equations(
    games: list[Game],
    weights: list[float],
    league_avg: float,
    team_index: dict[str, int],
) -> tuple[list[list[float]], list[float]]:
    """Build normal equations for the additive team-strength model."""
    team_count = len(team_index)
    size = 2 * team_count + 1
    matrix = [[0.0] * size for _ in range(size)]
    vector = [0.0] * size
    hfa_index = 2 * team_count

    for game, weight in zip(games, weights, strict=True):
        home = team_index[game.home]
        away = team_index[game.away]
        _add_observation(
            matrix,
            vector,
            ((home, 1.0), (team_count + away, 1.0), (hfa_index, 0.5)),
            game.home_score - league_avg,
            weight,
        )
        _add_observation(
            matrix,
            vector,
            ((away, 1.0), (team_count + home, 1.0), (hfa_index, -0.5)),
            game.away_score - league_avg,
            weight,
        )

    return matrix, vector


def _normalize_row(row: list[float], column: int) -> None:
    divisor = row[column]
    for j in range(column, len(row)):
        row[j] /= divisor


def _eliminate_row(row: list[float], pivot_row: list[float], column: int) -> None:
    factor = row[column]
    if factor == 0:
        return
    for j in range(column, len(row)):
        row[j] -= factor * pivot_row[j]


def _solve(matrix: list[list[float]], vector: list[float]) -> list[float]:
    """Solve a dense linear system with Gauss-Jordan elimination."""
    size = len(vector)
    augmented = [row[:] + [vector[i]] for i, row in enumerate(matrix)]

    for column in range(size):
        pivot = max(range(column, size), key=lambda row: abs(augmented[row][column]))
        if abs(augmented[pivot][column]) < 1e-9:
            raise ValueError("singular normal equations")
        augmented[column], augmented[pivot] = augmented[pivot], augmented[column]
        _normalize_row(augmented[column], column)
        for row in range(size):
            if row != column:
                _eliminate_row(augmented[row], augmented[column], column)

    return [augmented[i][size] for i in range(size)]


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _home_advantage(league_avg: float, hfa_points: float) -> float:
    """Convert a fitted point advantage into the multiplicative factor."""
    return _clamp(
        (league_avg + hfa_points / 2) / (league_avg - hfa_points / 2),
        0.9,
        1.15,
    )


def _form_adjustments(
    games: list[Game],
    coefficients: list[float],
    team_index: dict[str, int],
    league_avg: float,
) -> dict[str, tuple[float, float, int]]:
    """Average recent offensive/defensive residuals per team."""
    team_count = len(team_index)
    hfa_points = coefficients[2 * team_count]
    offense: dict[str, float] = defaultdict(float)
    defense: dict[str, float] = defaultdict(float)
    counts: dict[str, int] = defaultdict(int)

    for game in sorted(games, key=lambda g: g.date, reverse=True):
        home = team_index[game.home]
        away = team_index[game.away]
        pred_home = (
            league_avg
            + coefficients[home]
            + coefficients[team_count + away]
            + hfa_points / 2
        )
        pred_away = (
            league_avg
            + coefficients[away]
            + coefficients[team_count + home]
            - hfa_points / 2
        )
        entries = (
            (game.home, game.home_score - pred_home, game.away_score - pred_away),
            (game.away, game.away_score - pred_away, game.home_score - pred_home),
        )
        for name, offense_residual, defense_residual in entries:
            if counts[name] >= FORM_GAMES:
                continue
            offense[name] += offense_residual
            defense[name] += defense_residual
            counts[name] += 1

    return {
        name: (
            offense[name] / counts[name],
            defense[name] / counts[name],
            counts[name],
        )
        for name in counts
    }


def _build_ratings(
    team_index: dict[str, int],
    coefficients: list[float],
    league_avg: float,
    form: dict[str, tuple[float, float, int]],
) -> dict[str, TeamRating]:
    """Convert fitted coefficients and recent form into multiplicative ratings."""
    team_count = len(team_index)
    ratings: dict[str, TeamRating] = {}
    for name, index in team_index.items():
        offense = coefficients[index]
        defense = coefficients[team_count + index]
        form_offense, form_defense, form_count = form.get(name, (0.0, 0.0, 0))
        if form_count:
            scale = FORM_WEIGHT * form_count / FORM_GAMES
            offense += scale * form_offense
            defense += scale * form_defense
        ratings[name] = TeamRating(
            (league_avg + offense) / league_avg,
            (league_avg + defense) / league_avg,
        )
    return ratings


def _residual_sigma(
    games: list[Game],
    weights: list[float],
    coefficients: list[float],
    team_index: dict[str, int],
    league_avg: float,
) -> float:
    """Estimate score standard deviation from model residuals."""
    team_count = len(team_index)
    hfa_points = coefficients[2 * team_count]
    total = 0.0
    total_weight = 0.0

    for game, weight in zip(games, weights, strict=True):
        home = team_index[game.home]
        away = team_index[game.away]
        pred_home = (
            league_avg
            + coefficients[home]
            + coefficients[team_count + away]
            + hfa_points / 2
        )
        pred_away = (
            league_avg
            + coefficients[away]
            + coefficients[team_count + home]
            - hfa_points / 2
        )
        total += weight * (
            (game.home_score - pred_home) ** 2 + (game.away_score - pred_away) ** 2
        )
        total_weight += weight * 2

    return max(sqrt(total / total_weight), MIN_SIGMA)


def _team_index(games: list[Game]) -> dict[str, int]:
    """Map team names to deterministic coefficient indices."""
    names = {game.home for game in games} | {game.away for game in games}
    return {name: index for index, name in enumerate(sorted(names))}


def _fit_coefficients(
    games: list[Game],
    weights: list[float],
    league_avg: float,
    team_index: dict[str, int],
) -> list[float]:
    """Fit ridge-regularized offensive/defensive coefficients."""
    team_count = len(team_index)
    matrix, vector = _build_normal_equations(games, weights, league_avg, team_index)
    for index in range(2 * team_count):
        matrix[index][index] += RIDGE_LAMBDA
    prior_hfa = (
        2 * league_avg * (DEFAULT_HOME_ADVANTAGE - 1) / (DEFAULT_HOME_ADVANTAGE + 1)
    )
    matrix[2 * team_count][2 * team_count] += HFA_PRIOR_WEIGHT
    vector[2 * team_count] += HFA_PRIOR_WEIGHT * prior_hfa
    return _solve(matrix, vector)


def fit_model(games: list[Game]) -> StrengthModel:
    """Fit opponent-adjusted ratings with weighted ridge regression."""
    performance = [game for game in games if not game.forfeit]
    if not performance:
        return StrengthModel({}, 50.0, DEFAULT_HOME_ADVANTAGE, DEFAULT_SIGMA)

    reference_ts = max(game.date.timestamp() for game in performance)
    weights = [_recency_weight(game, reference_ts) for game in performance]
    league_avg = _weighted_league_avg(performance, weights)
    team_index = _team_index(performance)
    coefficients = _fit_coefficients(performance, weights, league_avg, team_index)

    hfa_points = coefficients[2 * len(team_index)]
    form = _form_adjustments(performance, coefficients, team_index, league_avg)
    ratings = _build_ratings(team_index, coefficients, league_avg, form)
    sigma = _residual_sigma(performance, weights, coefficients, team_index, league_avg)
    return StrengthModel(
        ratings,
        league_avg,
        _home_advantage(league_avg, hfa_points),
        sigma,
    )


def fit_strength(
    games: list[Game],
) -> tuple[dict[str, TeamStats], StrengthModel]:
    """Calculate standings stats and a fitted strength model."""
    teams: dict[str, TeamStats] = defaultdict(TeamStats)
    for game in games:
        record_game(
            teams,
            game.home,
            game.away,
            game.home_score,
            game.away_score,
            forfeit=game.forfeit,
        )
    return dict(teams), fit_model(games)


def _normal_cdf(value: float) -> float:
    return 0.5 * (1.0 + erf(value / sqrt(2.0)))


def predict_game(
    home: str,
    away: str,
    ratings: dict[str, TeamRating],
    league_avg: float,
    home_fatigue: float = 1.0,
    away_fatigue: float = 1.0,
    home_advantage: float = DEFAULT_HOME_ADVANTAGE,
    sigma: float = DEFAULT_SIGMA,
) -> tuple[Winner, int, int, float]:
    """Predict a game outcome and home-win probability."""
    home_rating = ratings.get(home, TeamRating(1.0, 1.0))
    away_rating = ratings.get(away, TeamRating(1.0, 1.0))

    h_off = home_rating.offense * home_fatigue
    h_def = home_rating.defense / home_fatigue
    a_off = away_rating.offense * away_fatigue
    a_def = away_rating.defense / away_fatigue

    hfa = sqrt(home_advantage)
    pred_home = league_avg * h_off * a_def * hfa
    pred_away = league_avg * a_off * h_def / hfa

    margin = pred_home - pred_away
    home_probability = _normal_cdf(margin / (sigma * sqrt(2.0)))
    home_probability = max(MIN_PROBABILITY, min(MAX_PROBABILITY, home_probability))
    ph = round(pred_home)
    pa = round(pred_away)

    if home_probability >= 0.5:
        winner: Winner = "home"
        ph = max(ph, pa + 1)
    else:
        winner = "away"
        pa = max(pa, ph + 1)

    return winner, ph, pa, home_probability


def game_times(played: list[Game]) -> dict[str, list[float]]:
    """Map each team to sorted played game timestamps, excluding forfeits."""
    times: dict[str, list[float]] = defaultdict(list)
    for game in played:
        if game.forfeit:
            continue
        timestamp = game.date.timestamp()
        times[game.home].append(timestamp)
        times[game.away].append(timestamp)
    return {name: sorted(values) for name, values in times.items()}


def fatigue(
    name: str, gt: float, game_times: dict[str, list[float]], threshold_s: float
) -> float:
    """Return the fatigue multiplier for a team playing at time ``gt``."""
    values = game_times.get(name, [])
    index = bisect_left(values, gt)
    if index == 0:
        return 1.0
    delta = gt - values[index - 1]
    return FATIGUE_PENALTY if delta <= threshold_s else 1.0
