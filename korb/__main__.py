#!/usr/bin/env python3
"""Basketball league CLI for DBB (Deutscher Basketball Bund) data.

Target: DBB Version ≤12.01.1-f733da5 (legacy JSP platform).
"""

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .core import LeagueInfo, read_games
from .download import discover_league_ids, download_league, wait_between_requests
from .ergebnisse import filter_ergebnisse, print_ergebnisse
from .predict import predict_standings, print_predicted_standings, print_predictions
from .schedule import filter_schedule, parse_schedule, print_schedule
from .standings import Standing, calculate_standings, print_table
from .team import get_team_results, print_bars, print_metrics, print_results


def _json_out(data: object) -> None:
    """Print data as formatted JSON."""
    print(json.dumps(data, indent=2, ensure_ascii=False))


def _liga_meta(
    league_info: LeagueInfo,
    ligaid: int | None,
) -> dict[str, object]:
    """Build liga metadata dict for JSON output.

    Args:
        league_info: League metadata from HTML.
        ligaid: Liga ID from CLI argument (may be None).

    Returns:
        Dict with liga_name, liga_number, and ligaid.
    """
    return {
        **league_info.to_dict(),
        "ligaid": ligaid,
    }


def _resolve_path(
    explicit: str | None, ligaid: int | None, filename: str, flag: str, label: str
) -> str:
    """Resolve an HTML path from an explicit flag value or --ligaid.

    Exits with an error if neither is provided.
    """
    if explicit is not None:
        return explicit
    if ligaid is None:
        print(
            f"Error: pass {flag} PATH or --ligaid LIGAID for {label}.",
            file=sys.stderr,
        )
        sys.exit(1)
    return str(Path("files") / str(ligaid) / filename)


def _resolve_results(args: argparse.Namespace, label: str) -> str:
    """Resolve the results HTML path from --results or --ligaid."""
    return _resolve_path(
        args.results, args.ligaid, "ergebnisse.html", "--results", label
    )


def _resolve_schedule(args: argparse.Namespace, label: str) -> str:
    """Resolve the schedule HTML path from --schedule or --ligaid."""
    return _resolve_path(
        args.schedule, args.ligaid, "spielplan.html", "--schedule", label
    )


def _positive_int(value: str) -> int:
    """Parse a CLI integer that must be at least 1."""
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return number


def cmd_standings(args: argparse.Namespace) -> None:
    """Handle 'standings' subcommand."""
    fp = _resolve_results(args, "standings")
    standings, league_info = calculate_standings(fp)
    if args.json:
        _json_out(
            {
                **_liga_meta(league_info, args.ligaid),
                "standings": [s.to_dict() for s in standings],
            }
        )
    else:
        print_table(standings, league_info.name)


def cmd_team(args: argparse.Namespace) -> None:
    """Handle 'team' subcommand."""
    fp = _resolve_results(args, "team results")
    results, league_info = get_team_results(args.name, fp)
    if args.json:
        data = [r.to_dict() for r in results]
        _json_out(
            {
                **_liga_meta(league_info, args.ligaid),
                "team": args.name,
                "results": data,
            }
        )
        return
    print_results(args.name, results, league_info.name)
    if args.bars:
        print()
        print_bars(results)
    if args.metrics or args.last_k:
        print()
        print_metrics(results, last_k=args.last_k)


def cmd_ergebnisse(args: argparse.Namespace) -> None:
    """Handle 'ergebnisse' subcommand."""
    fp = _resolve_results(args, "ergebnisse")
    games, league_info = read_games(fp)
    filtered = filter_ergebnisse(games, team=args.team)
    if args.json:
        ordered = sorted(filtered, key=lambda g: g.date)
        _json_out(
            {
                **_liga_meta(league_info, args.ligaid),
                "ergebnisse": [
                    {
                        "date": g.date.strftime("%d.%m.%Y %H:%M"),
                        "home": g.home,
                        "away": g.away,
                        "home_score": g.home_score,
                        "away_score": g.away_score,
                    }
                    for g in ordered
                ],
            }
        )
    else:
        print_ergebnisse(filtered, league_info.name)


def cmd_schedule(args: argparse.Namespace) -> None:
    """Handle 'schedule' subcommand."""
    html = _resolve_schedule(args, "schedule")
    games, league_info = parse_schedule(html)
    filtered = filter_schedule(
        games, show_all=args.all, pending=args.pending, team=args.team
    )
    if args.json:
        _json_out(
            {
                **_liga_meta(league_info, args.ligaid),
                "schedule": [g.to_dict() for g in filtered],
            }
        )
    else:
        print_schedule(filtered, league_info.name, b2b=args.b2b, reference=games)


def cmd_predict(args: argparse.Namespace) -> None:
    """Handle 'predict' subcommand."""
    rp = _resolve_results(args, "prediction results")
    sp = _resolve_schedule(args, "prediction schedule")

    standings, preds, league_info = predict_standings(rp, sp)
    if not preds:
        print(
            "Error: Season is finalized (no pending games). "
            "Prediction is not available.",
            file=sys.stderr,
        )
        sys.exit(1)
    if args.json:
        _json_out(
            {
                **_liga_meta(league_info, args.ligaid),
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
    return "█" * max(0, value // scale)


def _print_top_table(top: list[Standing], tw: int) -> None:
    """Print the ranked top-teams table."""
    print("\n" + "=" * 70)
    print("  Top Teams — current table")
    print("=" * 70)

    hdr = f"{'#':>2}  {'Team':<{tw}}  {'GP':>2}  {'Pts':>3}  {'Diff':>5}"
    print(hdr)
    print("-" * len(hdr))
    for i, s in enumerate(top, 1):
        st = s.stats
        diff_str = f"+{st.diff}" if st.diff > 0 else str(st.diff)
        print(f"{i:>2}  {s.name:<{tw}}  {st.gp:>2}  {st.pts:>3}  {diff_str:>5}")


def _print_points_chart(top: list[Standing], tw: int) -> None:
    """Print the ASCII points bar chart for the top teams."""
    pts_vals = [s.stats.pts for s in top]
    max_pts = max(pts_vals) if pts_vals else 0
    # Keep chart readable: 1 block per 1–2 points depending on scale.
    scale = 1 if max_pts <= 20 else max(1, max_pts // 20)
    print("\nStandings Points (scaled)")
    print("─────────────────────────")
    for s in top:
        pts = s.stats.pts
        print(f"{s.name:<{tw}}  {_blocks(pts, scale):<22}  {pts}")
    print(f"(scale: 1 block ≈ {scale} pts)")


def cmd_top(args: argparse.Namespace) -> None:
    """Handle 'top' subcommand."""
    fp = _resolve_results(args, "top")
    standings, league_info = calculate_standings(fp)
    top = standings[: args.n]

    if args.json:
        _json_out(
            {
                **_liga_meta(league_info, args.ligaid),
                "top": [s.to_dict() for s in top],
            }
        )
        return

    if not top:
        print("No standings data.")
        return

    tw = max(4, max(len(s.name) for s in top))
    _print_top_table(top, tw)
    _print_points_chart(top, tw)


def cmd_download(args: argparse.Namespace) -> None:
    """Handle 'download' subcommand."""
    if args.all and args.ligaid is None:
        ids = discover_league_ids()
        if not ids:
            print("No previously downloaded leagues found.", file=sys.stderr)
            sys.exit(1)
        print(f"Refreshing {len(ids)} league(s): {', '.join(str(i) for i in ids)}")
        for i, lid in enumerate(ids):
            if i > 0:
                wait_between_requests()
            print(f"\n--- Liga {lid} ---")
            download_league(lid)
        print("\nDone.")
        return
    if args.ligaid is None:
        print(
            "Error: --ligaid is required for download (or use --all).",
            file=sys.stderr,
        )
        sys.exit(1)
    download_league(args.ligaid)


def _build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""
    parser = argparse.ArgumentParser(
        prog="korb", description="Basketball league analysis tools"
    )
    parser.add_argument(
        "--version", "-V", action="version", version=f"%(prog)s {__version__}"
    )
    parser.add_argument(
        "--results",
        "-r",
        default=None,
        help="HTML results file path (files/<ligaid>/ergebnisse.html)",
    )
    parser.add_argument(
        "--schedule",
        "-s",
        default=None,
        help="HTML schedule file path (files/<ligaid>/spielplan.html)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON instead of formatted tables",
    )
    parser.add_argument(
        "--ligaid",
        "-l",
        type=int,
        default=None,
        help="Liga ID (e.g. 51491); resolves file paths automatically",
    )
    parser.add_argument(
        "--download",
        "-d",
        action="store_true",
        help="Download latest data before running the command",
    )

    subs = parser.add_subparsers(dest="command", required=True)

    p_st = subs.add_parser(
        "standings",
        help="Display league standings",
    )
    p_st.set_defaults(func=cmd_standings)

    p_tm = subs.add_parser(
        "team",
        help="Display results for a team",
    )
    p_tm.add_argument(
        "name",
        help="Team name (e.g., 'Hawks')",
    )
    p_tm.add_argument(
        "--bars",
        "-b",
        action="store_true",
        help="Show point differential bar chart",
    )
    p_tm.add_argument(
        "--last-k",
        type=_positive_int,
        default=None,
        help="Analyze only the most recent K games",
    )
    p_tm.add_argument(
        "--metrics",
        action="store_true",
        help="Show win-rate + margin quality metrics",
    )
    p_tm.set_defaults(func=cmd_team)

    p_er = subs.add_parser(
        "ergebnisse",
        help="Display game results",
    )
    p_er.add_argument(
        "--team",
        "-t",
        help="Filter by team name (partial match)",
    )
    p_er.set_defaults(func=cmd_ergebnisse)

    p_sc = subs.add_parser(
        "schedule",
        help="Display game schedule",
    )
    p_sc.add_argument(
        "--all",
        "-a",
        action="store_true",
        help="Show cancelled games",
    )
    p_sc.add_argument(
        "--pending",
        "-p",
        action="store_true",
        help="Show only pending games",
    )
    p_sc.add_argument(
        "--team",
        "-t",
        help="Filter by team name (partial match)",
    )
    p_sc.add_argument(
        "--b2b",
        action="store_true",
        help="Mark back-to-back fixtures (≤36h)",
    )
    p_sc.set_defaults(func=cmd_schedule)

    p_pr = subs.add_parser(
        "predict",
        help="Predict final standings",
    )
    p_pr.set_defaults(func=cmd_predict)

    p_top = subs.add_parser(
        "top",
        help="Show top teams from standings",
    )
    p_top.add_argument(
        "-n",
        type=_positive_int,
        default=3,
        help="How many teams to show (default: 3)",
    )
    p_top.set_defaults(func=cmd_top)

    p_dl = subs.add_parser(
        "download",
        help="Download results & schedule HTML",
    )
    p_dl.add_argument(
        "--all",
        "-a",
        action="store_true",
        help="Refresh all previously downloaded leagues",
    )
    p_dl.set_defaults(func=cmd_download)

    return parser


def main() -> None:
    """Entry point for CLI."""
    args = _build_parser().parse_args()

    if args.download and args.command != "download":
        if args.ligaid is None:
            print(
                "Error: --download requires --ligaid.",
                file=sys.stderr,
            )
            sys.exit(1)
        download_league(args.ligaid)

    args.func(args)


if __name__ == "__main__":
    main()
