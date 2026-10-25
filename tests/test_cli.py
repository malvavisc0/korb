"""Tests for korb.__main__ CLI commands."""

import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from korb import __version__
from korb.__main__ import (
    _positive_int,
    _resolve_results,
    _resolve_schedule,
    cmd_backtest,
    cmd_predict,
    cmd_schedule,
    cmd_standings,
    cmd_team,
    cmd_top,
    main,
)
from korb.core import DATE_FMT, LOCAL_TZ


def _make_args(**kwargs) -> argparse.Namespace:
    return argparse.Namespace(**kwargs)


class TestCmdStandings:
    def test_valid_file(self, ergebnisse_path, capsys):
        args = _make_args(results=ergebnisse_path, ligaid=None, json=False)
        cmd_standings(args)
        captured = capsys.readouterr()
        assert "Standings" in captured.out

    def test_missing_file(self, tmp_path):
        args = _make_args(results=str(tmp_path / "no.html"), ligaid=None, json=False)
        with pytest.raises(SystemExit):
            cmd_standings(args)

    def test_json_output(self, ergebnisse_path, capsys):
        args = _make_args(results=ergebnisse_path, ligaid=None, json=True)
        cmd_standings(args)
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert isinstance(data, dict)
        assert "liga_name" in data
        assert "liga_number" in data
        assert "ligaid" in data
        assert data["liga_name"] == "Test Bezirksliga"
        assert data["liga_number"] == 99999
        assert data["ligaid"] is None
        assert isinstance(data["standings"], list)


class TestCmdTeam:
    def test_valid_team(self, ergebnisse_path, capsys):
        args = _make_args(
            name="Alpha",
            results=ergebnisse_path,
            ligaid=None,
            json=False,
            bars=False,
            metrics=False,
            last_k=None,
        )
        cmd_team(args)
        captured = capsys.readouterr()
        assert "Alpha" in captured.out

    def test_no_match(self, ergebnisse_path, capsys):
        args = _make_args(
            name="NonExistent",
            results=ergebnisse_path,
            ligaid=None,
            json=False,
            bars=False,
            metrics=False,
            last_k=None,
        )
        cmd_team(args)
        captured = capsys.readouterr()
        assert "No results found" in captured.out

    def test_json_output(self, ergebnisse_path, capsys):
        args = _make_args(
            name="Alpha",
            results=ergebnisse_path,
            ligaid=None,
            json=True,
            bars=False,
            metrics=False,
            last_k=None,
        )
        cmd_team(args)
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert "liga_name" in data
        assert "liga_number" in data
        assert "ligaid" in data
        assert "team" in data
        assert "results" in data
        dates = [datetime.strptime(r["date"], DATE_FMT) for r in data["results"]]
        assert dates == sorted(dates)

    def test_bars_and_metrics(self, ergebnisse_path, capsys):
        args = _make_args(
            name="Alpha",
            results=ergebnisse_path,
            ligaid=None,
            json=False,
            bars=True,
            metrics=True,
            last_k=2,
        )
        cmd_team(args)
        out = capsys.readouterr().out
        assert "Metrics (quality profile)" in out
        assert "└" in out


class TestCmdSchedule:
    def test_pending_filter(self, spielplan_path, capsys, frozen_now):
        args = _make_args(
            schedule=spielplan_path,
            ligaid=None,
            all=False,
            pending=True,
            team=None,
            json=False,
            b2b=False,
        )
        cmd_schedule(args)
        captured = capsys.readouterr()
        assert "Schedule" in captured.out

    def test_team_filter(self, spielplan_path, capsys):
        args = _make_args(
            schedule=spielplan_path,
            ligaid=None,
            all=False,
            pending=False,
            team="Alpha",
            json=False,
            b2b=False,
        )
        cmd_schedule(args)
        captured = capsys.readouterr()
        assert "Alpha" in captured.out

    def test_b2b_uses_completed_history(self, tmp_path, capsys):
        now = datetime.now(LOCAL_TZ)
        rows = [
            (now - timedelta(hours=12), "Team A", "Team B"),
            (now + timedelta(hours=12), "Team A", "Team C"),
        ]
        html = "<html><head><title>Spielplan - Test (x)</title></head><body>"
        html += "<table>"
        for nr, (date, home, away) in enumerate(rows, 1):
            html += (
                f"<tr><td>{nr}</td><td>1</td>"
                f"<td>{date.strftime('%d.%m.%Y %H:%M')}</td>"
                f"<td>{home}</td><td>{away}</td><td>Halle</td></tr>"
            )
        html += "</table></body></html>"
        path = tmp_path / "spielplan.html"
        path.write_text(html)

        args = _make_args(
            schedule=str(path),
            ligaid=None,
            all=False,
            pending=True,
            team=None,
            json=False,
            b2b=True,
        )
        cmd_schedule(args)
        assert "⚡" in capsys.readouterr().out

    def test_json_output(self, spielplan_path, capsys):
        args = _make_args(
            schedule=spielplan_path,
            ligaid=None,
            all=False,
            pending=False,
            team=None,
            json=True,
            b2b=False,
        )
        cmd_schedule(args)
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert isinstance(data, dict)
        assert "liga_name" in data
        assert "liga_number" in data
        assert "ligaid" in data
        assert isinstance(data["schedule"], list)
        assert all(game["b2b"] is False for game in data["schedule"])

    def test_json_output_marks_b2b(self, tmp_path, capsys):
        now = datetime.now(LOCAL_TZ)
        rows = [
            (now + timedelta(hours=12), "Team A", "Team B"),
            (now + timedelta(hours=36), "Team A", "Team C"),
        ]
        html = "<html><head><title>Spielplan - Test (x)</title></head><body>"
        html += "<table>"
        for nr, (date, home, away) in enumerate(rows, 1):
            html += (
                f"<tr><td>{nr}</td><td>1</td>"
                f"<td>{date.strftime('%d.%m.%Y %H:%M')}</td>"
                f"<td>{home}</td><td>{away}</td><td>Halle</td></tr>"
            )
        html += "</table></body></html>"
        path = tmp_path / "spielplan.html"
        path.write_text(html)

        args = _make_args(
            schedule=str(path),
            ligaid=None,
            all=False,
            pending=False,
            team=None,
            json=True,
            b2b=True,
        )
        cmd_schedule(args)
        data = json.loads(capsys.readouterr().out)
        assert [game["b2b"] for game in data["schedule"]] == [False, True]


class TestCmdTop:
    def test_text_output(self, ergebnisse_path, capsys):
        args = _make_args(
            results=ergebnisse_path,
            ligaid=None,
            json=False,
            n=2,
        )
        cmd_top(args)
        out = capsys.readouterr().out
        assert "Top Teams" in out
        assert "1 block" in out

    def test_json_output(self, ergebnisse_path, capsys):
        args = _make_args(
            results=ergebnisse_path,
            ligaid=None,
            json=True,
            n=2,
        )
        cmd_top(args)
        data = json.loads(capsys.readouterr().out)
        assert "top" in data
        assert isinstance(data["top"], list)
        assert len(data["top"]) <= 2

    def test_empty_standings(self, tmp_path, capsys):
        f = tmp_path / "empty.html"
        f.write_text(
            "<html><head><title>Ergebnisse - League (x)</title></head>"
            "<body></body></html>"
        )
        args = _make_args(
            results=str(f),
            ligaid=None,
            json=False,
            n=3,
        )
        cmd_top(args)
        assert "No standings data." in capsys.readouterr().out


class TestMain:
    def test_dispatches_subcommand(self, monkeypatch, ergebnisse_path, capsys):
        monkeypatch.setattr(
            sys,
            "argv",
            ["korb", "--results", ergebnisse_path, "standings"],
        )
        main()
        assert "Standings" in capsys.readouterr().out

    def test_resolve_requires_path_or_ligaid(self):
        args = _make_args(results=None, schedule=None, ligaid=None)
        with pytest.raises(SystemExit):
            _resolve_results(args, "standings")

    def test_resolve_from_ligaid(self):
        args = _make_args(results=None, schedule=None, ligaid=12345)
        path = Path(_resolve_results(args, "standings"))
        assert path == Path("files") / "12345" / "ergebnisse.html"
        schedule = Path(_resolve_schedule(args, "prediction schedule"))
        assert schedule == Path("files") / "12345" / "spielplan.html"

    def test_positive_int_accepts_valid_value(self):
        assert _positive_int("7") == 7

    def test_positive_int_rejects_zero(self):
        with pytest.raises(argparse.ArgumentTypeError):
            _positive_int("0")

    def test_download_flag_downloads_league(self, monkeypatch, ergebnisse_path, capsys):
        calls = []
        monkeypatch.setattr(
            "korb.__main__.download_league",
            lambda ligaid: calls.append(ligaid),
        )
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "korb",
                "--ligaid",
                "12345",
                "--download",
                "--results",
                ergebnisse_path,
                "standings",
            ],
        )
        main()
        assert calls == [12345]
        assert "Standings" in capsys.readouterr().out

    def test_download_flag_requires_ligaid(self, monkeypatch):
        monkeypatch.setattr(
            sys,
            "argv",
            ["korb", "--download", "--results", "x.html", "standings"],
        )
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 1

    def test_backtest_requires_min_train_flag_value(self, monkeypatch, ergebnisse_path):
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "korb",
                "--results",
                ergebnisse_path,
                "backtest",
                "--min-train",
                "0",
            ],
        )
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 2

    def test_version_exits_zero(self, monkeypatch, capsys):
        monkeypatch.setattr(sys, "argv", ["korb", "--version"])
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 0
        assert __version__ in capsys.readouterr().out

    def test_top_rejects_non_positive_n(self, monkeypatch, ergebnisse_path):
        monkeypatch.setattr(
            sys,
            "argv",
            ["korb", "--results", ergebnisse_path, "top", "-n", "0"],
        )
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 2

    def test_team_rejects_non_positive_last_k(self, monkeypatch, ergebnisse_path):
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "korb",
                "--results",
                ergebnisse_path,
                "team",
                "Alpha",
                "--last-k",
                "0",
            ],
        )
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 2


class TestCmdPredict:
    def test_season_finalized_exits(
        self,
        ergebnisse_path,
        spielplan_finalized_path,
    ):
        args = _make_args(
            results=ergebnisse_path,
            schedule=spielplan_finalized_path,
            ligaid=None,
            json=False,
        )
        with pytest.raises(SystemExit):
            cmd_predict(args)

    def test_normal_execution(
        self, ergebnisse_path, spielplan_path, capsys, frozen_now
    ):
        args = _make_args(
            results=ergebnisse_path,
            schedule=spielplan_path,
            ligaid=None,
            json=False,
        )
        cmd_predict(args)
        captured = capsys.readouterr()
        assert "Predicted" in captured.out
        assert "%" in captured.out

    def test_json_output(self, ergebnisse_path, spielplan_path, capsys, frozen_now):
        args = _make_args(
            results=ergebnisse_path,
            schedule=spielplan_path,
            ligaid=None,
            json=True,
        )
        cmd_predict(args)
        data = json.loads(capsys.readouterr().out)
        assert data["predictions"]
        prediction = data["predictions"][0]
        assert set(prediction) >= {
            "nr",
            "date",
            "home",
            "away",
            "winner",
            "home_score",
            "away_score",
            "win_probability",
        }
        assert 0.0 <= prediction["win_probability"] <= 1.0

    def test_mismatched_leagues_exit(self, ergebnisse_path, tmp_path):
        schedule = tmp_path / "spielplan.html"
        schedule.write_text(
            "<html><head><title>Spielplan - Other (x; Liganr.: 11111)</title></head>"
            "<body><table><tr><td>1</td><td>1</td><td>01.06.2026 10:00</td>"
            "<td>Team Alpha</td><td>Team Beta</td><td>Halle</td></tr></table>"
            "</body></html>"
        )
        args = _make_args(
            results=ergebnisse_path,
            schedule=str(schedule),
            ligaid=None,
            json=False,
        )
        with pytest.raises(SystemExit):
            cmd_predict(args)


class TestCmdBacktest:
    def test_text_output(self, ergebnisse_path, capsys):
        args = _make_args(results=ergebnisse_path, ligaid=None, json=False, min_train=2)
        cmd_backtest(args)
        output = capsys.readouterr().out
        assert "Prediction Backtest" in output
        assert "Winner accuracy" in output

    def test_json_output(self, ergebnisse_path, capsys):
        args = _make_args(results=ergebnisse_path, ligaid=None, json=True, min_train=2)
        cmd_backtest(args)
        data = json.loads(capsys.readouterr().out)
        assert data["backtest"]["games"] > 0
        assert "brier" in data["backtest"]
