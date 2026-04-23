"""Tests for korb.ergebnisse module."""

import argparse
import json

import pytest

from korb.__main__ import cmd_ergebnisse
from korb.core import read_games
from korb.ergebnisse import filter_ergebnisse, print_ergebnisse


def _make_args(**kwargs) -> argparse.Namespace:
    return argparse.Namespace(**kwargs)


class TestFilterErgebnisse:
    def test_no_filter(self, ergebnisse_path):
        games, _ = read_games(ergebnisse_path)
        result = filter_ergebnisse(games)
        assert len(result) == len(games)

    def test_filter_by_team(self, ergebnisse_path):
        games, _ = read_games(ergebnisse_path)
        result = filter_ergebnisse(games, team="Alpha")
        assert len(result) > 0
        for g in result:
            assert "alpha" in g.home.lower() or "alpha" in g.away.lower()

    def test_filter_no_match(self, ergebnisse_path):
        games, _ = read_games(ergebnisse_path)
        result = filter_ergebnisse(games, team="NonExistent")
        assert len(result) == 0

    def test_filter_case_insensitive(self, ergebnisse_path):
        games, _ = read_games(ergebnisse_path)
        result = filter_ergebnisse(games, team="alpha")
        assert len(result) > 0


class TestPrintErgebnisse:
    def test_output_contains_header(self, ergebnisse_path, capsys):
        games, league_info = read_games(ergebnisse_path)
        print_ergebnisse(games, league_info.name)
        out = capsys.readouterr().out
        assert "Ergebnisse" in out
        assert "Test Bezirksliga" in out

    def test_output_contains_games(self, ergebnisse_path, capsys):
        games, league_info = read_games(ergebnisse_path)
        print_ergebnisse(games, league_info.name)
        out = capsys.readouterr().out
        assert "Team Alpha" in out
        assert "Team Beta" in out

    def test_empty_games(self, capsys):
        print_ergebnisse([], "Test League")
        out = capsys.readouterr().out
        assert "No game results found" in out


class TestCmdErgebnisse:
    def test_valid_file(self, ergebnisse_path, capsys):
        args = _make_args(results=ergebnisse_path, ligaid=None, json=False, team=None)
        cmd_ergebnisse(args)
        out = capsys.readouterr().out
        assert "Ergebnisse" in out

    def test_team_filter(self, ergebnisse_path, capsys):
        args = _make_args(
            results=ergebnisse_path, ligaid=None, json=False, team="Alpha"
        )
        cmd_ergebnisse(args)
        out = capsys.readouterr().out
        assert "Team Alpha" in out

    def test_json_output(self, ergebnisse_path, capsys):
        args = _make_args(results=ergebnisse_path, ligaid=None, json=True, team=None)
        cmd_ergebnisse(args)
        out = capsys.readouterr().out
        data = json.loads(out)
        assert "liga_name" in data
        assert "liga_number" in data
        assert "ligaid" in data
        assert "ergebnisse" in data
        assert isinstance(data["ergebnisse"], list)
        assert len(data["ergebnisse"]) > 0

    def test_missing_file(self, tmp_path):
        args = _make_args(
            results=str(tmp_path / "no.html"),
            ligaid=None,
            json=False,
            team=None,
        )
        with pytest.raises(SystemExit):
            cmd_ergebnisse(args)
