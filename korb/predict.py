"""Predict final standings for DBB (Deutscher Basketball Bund) leagues.

Uses a multiplicative efficiency model: each team's offensive and
defensive ratings (relative to league average) are multiplied to
predict matchup scores.  Recent games are weighted more heavily.
Target: DBB Version ≤12.01.1-f733da5 (legacy JSP platform).
"""

from collections import defaultdict
from math import exp, sqrt
from typing import Literal

from korb.core import Game, LeagueInfo, normalize_name, read_games
from korb.schedule import ScheduledGame, filter_schedule, parse_schedule
from korb.standings import (
    Standing,
    TeamStats,
    print_standings_rows,
    rank_standings,
    record_game,
)

Winner = Literal["home", "away"]
Prediction = tuple[ScheduledGame, Winner, int, int]

# Recency half-life in days
RECENCY_HALF_LIFE = 60.0
# Minimum games to trust a team's rating; below this, blend toward avg
MIN_GAMES = 3
HOME_ADVANTAGE_FACTOR = 1.03  # 3 % scoring boost for home team
# Back-to-back fatigue: ≤36 h between games → 5 % penalty
FATIGUE_THRESHOLD_H = 36
FATIGUE_PENALTY = 0.95  # multiplier on off_rating; inverse on def
# Recent form: last N games blended into ratings at FORM_WEIGHT
FORM_GAMES = 5
FORM_WEIGHT = 0.30


def _recency_weight(game: Game, ref_ts: float) -> float:
    """Exponential decay weight based on days since game.

    Args:
        game: Game to weight.
        ref_ts: Reference timestamp (usually most recent game).

    Returns:
        Weight between 0 and 1, decreasing with age.
    """
    days_ago = (ref_ts - game.date.timestamp()) / 86400
    days_ago = max(days_ago, 0)
    return exp(-0.693 * days_ago / RECENCY_HALF_LIFE)


def calc_strength(
    fp: str,
) -> tuple[dict[str, TeamStats], dict[str, tuple[float, float]], float]:
    """Calculate team strength from completed games in a results file.

    Args:
        fp: HTML results file path.

    Returns:
        Tuple of (teams, ratings, league_avg) where:
            teams: unweighted TeamStats per team
            ratings: dict mapping team to (off_rating, def_rating)
            league_avg: league-wide weighted avg points per game
    """
    games, _ = read_games(fp)
    return _calc_strength(games)


def _calc_strength(
    games: list[Game],
) -> tuple[dict[str, TeamStats], dict[str, tuple[float, float]], float]:
    """Calculate team strength from completed games."""
    if not games:
        return {}, {}, 50.0

    ref_ts = max(g.date.timestamp() for g in games)

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

    w_pf: dict[str, float] = defaultdict(float)
    w_pa: dict[str, float] = defaultdict(float)
    w_gp: dict[str, float] = defaultdict(float)

    for game in games:
        w = _recency_weight(game, ref_ts)
        for name, pf, pa in [
            (game.home, game.home_score, game.away_score),
            (game.away, game.away_score, game.home_score),
        ]:
            w_pf[name] += pf * w
            w_pa[name] += pa * w
            w_gp[name] += w

    total_pf = sum(w_pf.values())
    total_gp = sum(w_gp.values())
    league_avg = total_pf / total_gp if total_gp else 50.0

    form_pf, form_pa, form_gp = _calc_form_totals(games)

    ratings = _build_ratings(
        w_pf,
        w_pa,
        w_gp,
        league_avg,
        teams,
        form_pf,
        form_pa,
        form_gp,
    )
    return dict(teams), ratings, league_avg


def _calc_form_totals(
    games: list[Game],
) -> tuple[dict[str, float], dict[str, float], dict[str, int]]:
    """Sum points for/against from each team's last FORM_GAMES games.

    Games are assumed sorted newest-first (as returned by read_games).
    """
    seen: dict[str, int] = defaultdict(int)
    fpf: dict[str, float] = defaultdict(float)
    fpa: dict[str, float] = defaultdict(float)
    fgp: dict[str, int] = defaultdict(int)

    for game in games:  # newest first
        for name, pf, pa in [
            (game.home, game.home_score, game.away_score),
            (game.away, game.away_score, game.home_score),
        ]:
            if seen[name] < FORM_GAMES:
                fpf[name] += pf
                fpa[name] += pa
                fgp[name] += 1
                seen[name] += 1
    return fpf, fpa, fgp


def _build_ratings(
    w_pf: dict[str, float],
    w_pa: dict[str, float],
    w_gp: dict[str, float],
    league_avg: float,
    teams: dict[str, TeamStats],
    form_pf: dict[str, float],
    form_pa: dict[str, float],
    form_gp: dict[str, int],
) -> dict[str, tuple[float, float]]:
    """Build per-team (off_rating, pts_allowed_rating) dict.

    Ratings are a blend of recency-weighted season data and recent form
    (last FORM_GAMES games at FORM_WEIGHT).

    - off_rating: >1 means team scores above league avg (good offense).
    - pts_allowed_rating: >1 means team *allows* above league avg
      (bad defense); opponents score more against this team.

    Teams with fewer than MIN_GAMES are blended toward 1.0 (league avg)
    to avoid wild predictions on thin data.

    Returns:
        Dict mapping team name to (off_rating, pts_allowed_rating).
    """
    ratings: dict[str, tuple[float, float]] = {}
    for name, gp_weight in w_gp.items():
        avg_pf = w_pf[name] / gp_weight
        avg_pa = w_pa[name] / gp_weight
        raw_off = avg_pf / league_avg
        raw_def = avg_pa / league_avg

        gp = teams[name].gp if name in teams else 0
        if gp < MIN_GAMES:
            blend = gp / MIN_GAMES
            raw_off = blend * raw_off + (1 - blend) * 1.0
            raw_def = blend * raw_def + (1 - blend) * 1.0

        # Blend in recent form if team has enough form games
        fg = form_gp.get(name, 0)
        if fg >= MIN_GAMES:
            f_off = (form_pf[name] / fg) / league_avg
            f_def = (form_pa[name] / fg) / league_avg
            raw_off = (1 - FORM_WEIGHT) * raw_off + FORM_WEIGHT * f_off
            raw_def = (1 - FORM_WEIGHT) * raw_def + FORM_WEIGHT * f_def

        ratings[name] = (raw_off, raw_def)
    return ratings


def predict_game(
    home: str,
    away: str,
    ratings: dict[str, tuple[float, float]],
    league_avg: float,
    home_fatigue: float = 1.0,
    away_fatigue: float = 1.0,
) -> tuple[Winner, int, int]:
    """Predict game outcome using multiplicative efficiency model.

    Home advantage is applied symmetrically (zero-sum):
        pred_home = league_avg × home_off × away_def × √HFA
        pred_away = league_avg × away_off × home_def / √HFA

    Fatigue multipliers (<1.0) reduce offense and worsen defense
    for teams playing back-to-back.

    Args:
        home: Home team name.
        away: Away team name.
        ratings: Dict mapping team to (off_rating, pts_allowed_rating).
        league_avg: League average points per game.
        home_fatigue: Multiplier for home team (1.0 = fresh, <1.0 = tired).
        away_fatigue: Multiplier for away team (1.0 = fresh, <1.0 = tired).

    Returns:
        Tuple of (winner, home_score, away_score).
    """
    h_off, h_def = ratings.get(home, (1.0, 1.0))
    a_off, a_def = ratings.get(away, (1.0, 1.0))

    h_off *= home_fatigue
    h_def /= home_fatigue
    a_off *= away_fatigue
    a_def /= away_fatigue

    hfa = sqrt(HOME_ADVANTAGE_FACTOR)
    pred_home = league_avg * h_off * a_def * hfa
    pred_away = league_avg * a_off * h_def / hfa

    ph = round(pred_home)
    pa = round(pred_away)

    if ph == pa:
        if pred_home >= pred_away:
            ph += 1  # home advantage tiebreak
        else:
            pa += 1

    if ph > pa:
        return "home", ph, pa
    return "away", ph, pa


def _copy_stats(teams_base: dict[str, TeamStats]) -> dict[str, TeamStats]:
    """Deep-copy current team stats into a fresh defaultdict."""
    teams: dict[str, TeamStats] = defaultdict(TeamStats)
    for name, st in teams_base.items():
        t = teams[name]
        t.gp, t.w, t.l, t.d = st.gp, st.w, st.l, st.d
        t.pf, t.pa, t.penalty = st.pf, st.pa, st.penalty
    return teams


def _pending_games(html_path: str, played: list[Game]) -> list[ScheduledGame]:
    """Return scheduled games not already present in results."""
    played_numbers = {g.nr for g in played if g.nr is not None}
    played_keys = {
        (normalize_name(g.home), normalize_name(g.away), g.date.strftime("%d.%m.%Y"))
        for g in played
    }
    schedule, _ = parse_schedule(html_path)
    pending = [
        g
        for g in filter_schedule(schedule)
        if g.nr not in played_numbers
        and (
            normalize_name(g.home),
            normalize_name(g.away),
            g.date.strftime("%d.%m.%Y"),
        )
        not in played_keys
    ]
    pending.sort(key=lambda g: g.date)
    return pending


def _last_game_times(played: list[Game]) -> dict[str, float]:
    """Map each team to the timestamp of its most recent played game."""
    last_game_ts: dict[str, float] = {}
    for g in played:
        ts = g.date.timestamp()
        for name in (g.home, g.away):
            if ts > last_game_ts.get(name, 0):
                last_game_ts[name] = ts
    return last_game_ts


def _fatigue(
    name: str, gt: float, last_game_ts: dict[str, float], threshold_s: float
) -> float:
    """Return the fatigue multiplier for a team playing at time ``gt``."""
    if name in last_game_ts and (gt - last_game_ts[name]) <= threshold_s:
        return FATIGUE_PENALTY
    return 1.0


def predict_standings(
    results_path: str,
    html_path: str,
) -> tuple[list[Standing], list[Prediction], LeagueInfo]:
    """Predict final standings based on remaining games.

    Completed games (from results file) are cross-referenced against
    the schedule to avoid double-counting.

    Args:
        results_path: HTML results file path.
        html_path: HTML schedule file path.

    Returns:
        Tuple of (standings, predictions, league_info) where standings
        is the predicted final standings, predictions is a list of
        (game, winner, home_score, away_score) tuples, and league_info
        contains league metadata.
    """
    played, league_info = read_games(results_path)
    teams_base, ratings, league_avg = _calc_strength(played)
    teams = _copy_stats(teams_base)
    pending = _pending_games(html_path, played)

    last_game_ts = _last_game_times(played)
    threshold_s = FATIGUE_THRESHOLD_H * 3600

    preds: list[Prediction] = []
    for game in pending:
        gt = game.date.timestamp()
        h_fat = _fatigue(game.home, gt, last_game_ts, threshold_s)
        a_fat = _fatigue(game.away, gt, last_game_ts, threshold_s)

        winner, hs, as_ = predict_game(
            game.home,
            game.away,
            ratings,
            league_avg,
            home_fatigue=h_fat,
            away_fatigue=a_fat,
        )

        last_game_ts[game.home] = gt
        last_game_ts[game.away] = gt
        preds.append((game, winner, hs, as_))
        record_game(teams, game.home, game.away, hs, as_, forfeit=False)

    standings = [Standing(n, s) for n, s in teams.items()]
    rank_games = list(played) + [
        Game(
            nr=game.nr,
            date=game.date,
            home=game.home,
            away=game.away,
            home_score=hs,
            away_score=as_,
        )
        for game, _, hs, as_ in preds
    ]
    return rank_standings(standings, rank_games), preds, league_info


def print_predictions(
    preds: list[Prediction],
) -> None:
    """Print predicted game outcomes.

    Args:
        preds: List of (game, winner, home_score, away_score) tuples.
    """
    print("\n" + "=" * 70)
    print("  Predicted Remaining Games")
    print("=" * 70)

    if not preds:
        print("  No pending games.")
        return

    sorted_preds = sorted(preds, key=lambda x: x[0].date)
    hw = max(len(g.home) for g, *_ in sorted_preds)
    aw = max(len(g.away) for g, *_ in sorted_preds)

    for game, winner, hs, as_ in sorted_preds:
        date_str = game.date.strftime("%d.%m.%y %H:%M")
        tag = f"<- {game.home}" if winner == "home" else f"-> {game.away}"
        print(
            f"  {date_str}  {game.home:<{hw}}  "
            f"{hs:>3} : {as_:<3}  "
            f"{game.away:<{aw}}  {tag}"
        )


def print_predicted_standings(standings: list[Standing]) -> None:
    """Print predicted final standings.

    Args:
        standings: List of Standing objects to display.
    """
    print("\n" + "=" * 70)
    print("  Predicted Final Standings")
    print("=" * 70)

    if not standings:
        print("No predictions.")
        return

    print_standings_rows(standings)
    print()
