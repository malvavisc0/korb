"""Tests for korb.__main__ CLI commands."""

import argparse

import pytest

from korb.__main__ import cmd_predict, cmd_schedule, cmd_standings, cmd_team


def _make_args(**kwargs) -> argparse.Namespace:
    return argparse.Namespace(**kwargs)


class TestCmdStandings:
    def test_valid_file(self, ergebnisse_path, capsys):
        args = _make_args(results=ergebnisse_path, liganr=None, json=False)
        cmd_standings(args)
        captured = capsys.readouterr()
        assert "Standings" in captured.out

    def test_missing_file(self, tmp_path):
        args = _make_args(results=str(tmp_path / "no.html"), liganr=None, json=False)
        with pytest.raises(SystemExit):
            cmd_standings(args)

    def test_json_output(self, ergebnisse_path, capsys):
        args = _make_args(results=ergebnisse_path, liganr=None, json=True)
        cmd_standings(args)
        captured = capsys.readouterr()
        import json

        data = json.loads(captured.out)
        assert isinstance(data, list)


class TestCmdTeam:
    def test_valid_team(self, ergebnisse_path, capsys):
        args = _make_args(
            name="Alpha",
            results=ergebnisse_path,
            liganr=None,
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
            liganr=None,
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
            liganr=None,
            json=True,
            bars=False,
            metrics=False,
            last_k=None,
        )
        cmd_team(args)
        captured = capsys.readouterr()
        import json

        data = json.loads(captured.out)
        assert "team" in data
        assert "results" in data


class TestCmdSchedule:
    def test_pending_filter(self, spielplan_path, capsys):
        args = _make_args(
            html=spielplan_path,
            liganr=None,
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
            html=spielplan_path,
            liganr=None,
            all=False,
            pending=False,
            team="Alpha",
            json=False,
            b2b=False,
        )
        cmd_schedule(args)
        captured = capsys.readouterr()
        assert "Alpha" in captured.out

    def test_json_output(self, spielplan_path, capsys):
        args = _make_args(
            html=spielplan_path,
            liganr=None,
            all=False,
            pending=False,
            team=None,
            json=True,
            b2b=False,
        )
        cmd_schedule(args)
        captured = capsys.readouterr()
        import json

        data = json.loads(captured.out)
        assert isinstance(data, list)


class TestCmdPredict:
    def test_season_finalized_exits(
        self,
        ergebnisse_path,
        spielplan_finalized_path,
    ):
        args = _make_args(
            results=ergebnisse_path,
            html=spielplan_finalized_path,
            liganr=None,
            json=False,
        )
        with pytest.raises(SystemExit):
            cmd_predict(args)

    def test_normal_execution(self, ergebnisse_path, spielplan_path, capsys):
        args = _make_args(
            results=ergebnisse_path,
            html=spielplan_path,
            liganr=None,
            json=False,
        )
        cmd_predict(args)
        captured = capsys.readouterr()
        assert "Predicted" in captured.out
