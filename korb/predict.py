"""Predict final standings for DBB (Deutscher Basketball Bund) leagues.

Uses a multiplicative efficiency model: each team's offensive and
defensive ratings (relative to league average) are multiplied to
predict matchup scores.  Recent games are weighted more heavily.
Target: DBB Version ≤11.50.0-623b018 (legacy JSP platform).
"""

from collections import defaultdict
from math import exp, sqrt

from korb.core import Game, LeagueInfo, read_games
from korb.schedule import ScheduledGame, filter_schedule, parse_schedule
from korb.standings import Standing, TeamStats

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
    if days_ago < 0:
        days_ago = 0
    return exp(-0.693 * days_ago / RECENCY_HALF_LIFE)


def calc_strength(
    fp: str,
) -> tuple[dict[str, TeamStats], dict[str, tuple[float, float]], float]:
    """Calculate team strength from completed games.

    Args:
        fp: HTML results file path.

    Returns:
        Tuple of (teams, ratings, league_avg) where:
            teams: unweighted TeamStats per team
            ratings: dict mapping team to (off_rating, def_rating)
            league_avg: league-wide weighted avg points per game
    """
    games, _ = read_games(fp)
    if not games:
        return {}, {}, 50.0

    ref_ts = max(g.date.timestamp() for g in games)

    # Unweighted stats for win / loss record
    teams: dict[str, TeamStats] = defaultdict(TeamStats)
    for game in games:
        h, a = teams[game.home], teams[game.away]
        h.gp += 1
        a.gp += 1
        h.pf += game.home_score
        h.pa += game.away_score
        a.pf += game.away_score
        a.pa += game.home_score
        if game.home_score > game.away_score:
            h.w += 1
            a.l += 1
        elif game.home_score < game.away_score:
            a.w += 1
            h.l += 1
        else:
            h.d += 1
            a.d += 1

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
    for name in w_gp:
        avg_pf = w_pf[name] / w_gp[name]
        avg_pa = w_pa[name] / w_gp[name]
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
) -> tuple[str, int, int]:
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


def predict_standings(
    results_path: str,
    html_path: str,
) -> tuple[list[Standing], list[tuple[ScheduledGame, str, int, int]], LeagueInfo]:
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
    rp = results_path
    teams_base, ratings, league_avg = calc_strength(rp)
    teams: dict[str, TeamStats] = defaultdict(TeamStats)

    for name, st in teams_base.items():
        t = teams[name]
        t.gp = st.gp
        t.w = st.w
        t.l = st.l
        t.d = st.d
        t.pf = st.pf
        t.pa = st.pa

    played, league_info = read_games(rp)
    played_keys: set[tuple[str, str, str]] = {
        (g.home, g.away, g.date.strftime("%d.%m.%Y")) for g in played
    }

    schedule, _ = parse_schedule(html_path)
    pending = [
        g
        for g in filter_schedule(schedule, pending=True)
        if (g.home, g.away, g.date.strftime("%d.%m.%Y")) not in played_keys
    ]

    pending.sort(key=lambda g: g.date)
    last_game_ts: dict[str, float] = {}
    for g in played:
        ts = g.date.timestamp()
        for name in (g.home, g.away):
            if ts > last_game_ts.get(name, 0):
                last_game_ts[name] = ts

    threshold_s = FATIGUE_THRESHOLD_H * 3600

    preds: list[tuple[ScheduledGame, str, int, int]] = []
    for game in pending:
        gt = game.date.timestamp()
        h_fat = (
            FATIGUE_PENALTY
            if game.home in last_game_ts
            and (gt - last_game_ts[game.home]) <= threshold_s
            else 1.0
        )
        a_fat = (
            FATIGUE_PENALTY
            if game.away in last_game_ts
            and (gt - last_game_ts[game.away]) <= threshold_s
            else 1.0
        )

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

        h, a = teams[game.home], teams[game.away]
        h.gp += 1
        a.gp += 1
        h.pf += hs
        h.pa += as_
        a.pf += as_
        a.pa += hs

        if winner == "home":
            h.w += 1
            a.l += 1
        elif winner == "away":
            a.w += 1
            h.l += 1
        else:
            h.d += 1
            a.d += 1

    standings = [Standing(n, s) for n, s in teams.items()]
    standings.sort(
        key=lambda s: (-s.stats.pts, -s.stats.diff, -s.stats.pf),
    )
    return standings, preds, league_info


def print_predictions(
    preds: list[tuple[ScheduledGame, str, int, int]],
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
        if winner == "home":
            tag = f"<- {game.home}"
        elif winner == "away":
            tag = f"-> {game.away}"
        else:
            tag = "== Draw"
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

    tw = max(4, max(len(s.name) for s in standings))
    hdr = (
        f"{'#':>2}  {'Team':<{tw}}  "
        f"{'GP':>3} {'W':>3} {'L':>3} {'D':>3}  "
        f"{'PF':>5} {'PA':>5} {'Diff':>6} {'Pts':>4}  "
        f"{'Avg PF':>7} {'Avg PA':>7}"
    )
    print(hdr)
    print("-" * len(hdr))

    for i, s in enumerate(standings, 1):
        d = s.stats.diff
        diff_str = f"+{d}" if d > 0 else str(d)
        print(
            f"{i:>2}  {s.name:<{tw}}  "
            f"{s.stats.gp:>3} {s.stats.w:>3} "
            f"{s.stats.l:>3} {s.stats.d:>3}  "
            f"{s.stats.pf:>5} {s.stats.pa:>5} "
            f"{diff_str:>6} {s.stats.pts:>4}  "
            f"{s.stats.avg_pf:>7.1f} {s.stats.avg_pa:>7.1f}"
        )
    print()
