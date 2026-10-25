"""Tests for korb.__main__ CLI commands."""

import argparse
import json
import sys
from datetime import datetime, timedelta

import pytest

from korb import __version__
from korb.__main__ import (
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
