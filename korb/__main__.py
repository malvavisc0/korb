#!/usr/bin/env python3
"""Basketball league CLI for DBB (Deutscher Basketball Bund) data.

Target: DBB Version ≤11.50.0-623b018 (legacy JSP platform).
"""

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

from .predict import predict_standings, print_predicted_standings, print_predictions
from .schedule import (
    filter_schedule,
    is_season_finalized,
    parse_schedule,
    print_schedule,
)
from .standings import calculate_standings, print_table
from .team import get_team_results, print_bars, print_metrics, print_results


def _json_out(data: object) -> None:
    """Print data as formatted JSON."""
    print(json.dumps(data, indent=2, ensure_ascii=False))


def cmd_standings(args: argparse.Namespace) -> None:
    """Handle 'standings' subcommand."""
    fp = args.results
    if fp is None:
        if args.liganr is None:
            print(
                "Error: pass --results PATH or --liganr LIGANR " "for standings.",
                file=sys.stderr,
            )
            sys.exit(1)
        fp = str(Path("files") / str(args.liganr) / "ergebnisse.html")

    standings, league_name = calculate_standings(fp)
    if args.json:
        _json_out([s.to_dict() for s in standings])
    else:
        print_table(standings, league_name)


def cmd_team(args: argparse.Namespace) -> None:
    """Handle 'team' subcommand."""
    fp = args.results
    if fp is None:
        if args.liganr is None:
            print(
                "Error: pass --results PATH or --liganr LIGANR " "for team results.",
                file=sys.stderr,
            )
            sys.exit(1)
        fp = str(Path("files") / str(args.liganr) / "ergebnisse.html")

    results, league_name = get_team_results(args.name, fp)
    if args.json:
        data = [r.to_dict() for r in results]
        _json_out({"team": args.name, "results": data})
        return
    print_results(args.name, results, league_name)
    if args.bars:
        print()
        print_bars(results)
    if args.metrics or args.last_k:
        print()
        print_metrics(results, league_name, last_k=args.last_k)


def cmd_schedule(args: argparse.Namespace) -> None:
    """Handle 'schedule' subcommand."""
    html = args.html
    if html is None:
        if args.liganr is None:
            print(
                "Error: pass --html PATH or --liganr LIGANR for schedule.",
                file=sys.stderr,
            )
            sys.exit(1)
        html = str(Path("files") / str(args.liganr) / "spielplan.html")

    games, league_name = parse_schedule(html)
    filtered = filter_schedule(
        games, show_all=args.all, pending=args.pending, team=args.team
    )
    if args.json:
        _json_out([g.to_dict() for g in filtered])
    else:
        print_schedule(filtered, league_name, b2b=args.b2b)


def cmd_predict(args: argparse.Namespace) -> None:
    """Handle 'predict' subcommand."""
    rp = args.results
    sp = args.html
    if rp is None or sp is None:
        if args.liganr is None:
            print(
                "Error: pass --results PATH and --html PATH, "
                "or provide --liganr LIGANR.",
                file=sys.stderr,
            )
            sys.exit(1)
        base = Path("files") / str(args.liganr)
        rp = rp or str(base / "ergebnisse.html")
        sp = sp or str(base / "spielplan.html")

    # Check if season is finalized
    finalized, pending_count = is_season_finalized(sp)
    if finalized:
        print(
            "Error: Season is finalized (no pending games). "
            "Prediction is not available.",
            file=sys.stderr,
        )
        sys.exit(1)

    standings, preds = predict_standings(rp, sp)
    if args.json:
        _json_out(
            {
                "predictions": [
                    {
                        "home": g.home,
                        "away": g.away,
                        "winner": w,
                        "home_score": hs,
                        "away_score": aws,
                    }
                    for g, w, hs, aws in preds
                ],
                "standings": [s.to_dict() for s in standings],
            }
        )
    else:
        print_predictions(preds)
        print_predicted_standings(standings)


def _blocks(value: int, scale: int) -> str:
    if scale <= 0:
        scale = 1
    return "█" * max(0, value // scale)


def cmd_top(args: argparse.Namespace) -> None:
    """Handle 'top' subcommand."""

    fp = args.results
    if fp is None:
        if args.liganr is None:
            print(
                "Error: pass --results PATH or --liganr LIGANR for top.",
                file=sys.stderr,
            )
            sys.exit(1)
        fp = str(Path("files") / str(args.liganr) / "ergebnisse.html")

    standings, _league_name = calculate_standings(fp)
    top = standings[: args.n]

    if args.json:
        _json_out([s.to_dict() for s in top])
        return

    tw = max(4, max(len(s.name) for s in top))
    print("\n" + "=" * 70)
    print("  Top Teams — current table")
    print("=" * 70)

    hdr = f"{'#':>2}  {'Team':<{tw}}  {'GP':>2}  {'Pts':>3}  {'Diff':>5}"
    print(hdr)
    print("-" * len(hdr))
    for i, s in enumerate(top, 1):
        st = s.stats
        diff = st.diff
        diff_str = f"+{diff}" if diff > 0 else str(diff)
        print(f"{i:>2}  {s.name:<{tw}}  {st.gp:>2}  {st.pts:>3}  {diff_str:>5}")

    # Points bar chart (ASCII)
    pts_vals = [s.stats.pts for s in top]
    max_pts = max(pts_vals) if pts_vals else 0
    # Keep chart readable: 1 block per 1–2 points depending on scale.
    scale = 1 if max_pts <= 20 else max(1, max_pts // 20)
    print("\nStandings Points (scaled)")
    print("─────────────────────────")
    for s in top:
        st = s.stats
        pts = st.pts
        print(f"{s.name:<{tw}}  {_blocks(pts, scale):<22}  {pts}")
    print(f"(scale: 1 block ≈ {scale} pts)")


_BASE = "https://www.basketball-bund.net/public"
_RESULTS_URL = (
    f"{_BASE}/ergebnisse.jsp?print=1"
    "&viewDescKey=sport.dbb.liga.ErgebnisseViewPublic"
    "/index.jsp_&liga_id={liga_id}"
)
_SCHEDULE_URL = (
    f"{_BASE}/spielplan_list.jsp?print=1"
    "&viewDescKey=sport.dbb.liga.SpielplanViewPublic"
    "/index.jsp_&liga_id={liga_id}"
)


def cmd_download(args: argparse.Namespace) -> None:
    """Handle 'download' subcommand."""
    out_root = Path("files")
    out_root.mkdir(exist_ok=True)

    # New layout: keep per-league artifacts in their own subfolder.
    # Example: files/<liganr>/ergebnisse.html + files/<liganr>/spielplan.html
    out = out_root / str(args.liganr)
    out.mkdir(exist_ok=True)
    targets = [
        (_RESULTS_URL.format(liga_id=args.liganr), out / "ergebnisse.html"),
        (_SCHEDULE_URL.format(liga_id=args.liganr), out / "spielplan.html"),
    ]
    for url, dest in targets:
        print(f"Downloading {dest.name} ...", end=" ", flush=True)
        try:
            urllib.request.urlretrieve(url, dest)
            print("OK")
        except urllib.error.URLError as e:
            print(f"FAILED: {e}", file=sys.stderr)
            sys.exit(1)


def main() -> None:
    """Entry point for CLI."""
    parser = argparse.ArgumentParser(
        prog="korb", description="Basketball league analysis tools"
    )
    parser.add_argument(
        "--results",
        "-r",
        default=None,
        help="HTML results file path (files/<liganr>/ergebnisse.html)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON instead of formatted tables",
    )

    subs = parser.add_subparsers(dest="command", required=True)

    p_st = subs.add_parser("standings", help="Display league standings")
    p_st.add_argument(
        "--liganr",
        type=int,
        help="Liga ID; uses files/<liganr>/ergebnisse.html",
    )
    p_st.set_defaults(func=cmd_standings)

    p_tm = subs.add_parser("team", help="Display results for a team")
    p_tm.add_argument("name", help="Team name (e.g., 'TV 1877 Lauf')")
    p_tm.add_argument(
        "--liganr",
        type=int,
        help="Liga ID; uses files/<liganr>/ergebnisse.html",
    )
    p_tm.add_argument(
        "--bars", "-b", action="store_true", help="Show point differential bar chart"
    )
    p_tm.add_argument(
        "--last-k",
        type=int,
        default=None,
        help="Analyze only the most recent K games (newest-first)",
    )
    p_tm.add_argument(
        "--metrics",
        action="store_true",
        help="Show win-rate + margin quality metrics (respects --last-k)",
    )
    p_tm.set_defaults(func=cmd_team)

    p_sc = subs.add_parser("schedule", help="Display game schedule")
    p_sc.add_argument(
        "--html",
        default=None,
        help="Schedule HTML file (files/<liganr>/spielplan.html)",
    )
    p_sc.add_argument(
        "--liganr",
        type=int,
        help="Liga ID; uses files/<liganr>/spielplan.html",
    )
    p_sc.add_argument("--all", "-a", action="store_true", help="Show cancelled games")
    p_sc.add_argument(
        "--pending",
        "-p",
        action="store_true",
        help="Show only pending games",
    )
    p_sc.add_argument("--team", "-t", help="Filter by team name (partial match)")
    p_sc.add_argument(
        "--b2b",
        action="store_true",
        help="Mark fixtures that include a back-to-back (≤36h)",
    )
    p_sc.set_defaults(func=cmd_schedule)

    p_pr = subs.add_parser("predict", help="Predict final standings")
    p_pr.add_argument(
        "--html",
        default=None,
        help="Schedule HTML file (files/<liganr>/spielplan.html)",
    )
    p_pr.add_argument(
        "--liganr",
        type=int,
        help="Liga ID; uses files/<liganr>/ergebnisse.html + spielplan.html",
    )
    p_pr.set_defaults(func=cmd_predict)

    p_top = subs.add_parser("top", help="Show top teams from current standings")
    p_top.add_argument(
        "--liganr",
        type=int,
        help="Liga ID; uses files/<liganr>/ergebnisse.html",
    )
    p_top.add_argument(
        "-n",
        type=int,
        default=3,
        help="How many teams to show (default: 3)",
    )
    p_top.set_defaults(func=cmd_top)

    p_dl = subs.add_parser(
        "download",
        help="Download results & schedule HTML",
    )
    p_dl.add_argument(
        "liganr",
        type=int,
        help="Liga ID (e.g. 51491)",
    )
    p_dl.set_defaults(func=cmd_download)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
