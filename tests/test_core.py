"""Tests for korb.core module."""

from datetime import datetime

from korb.core import (
    LeagueInfo,
    _HTMLResultsParser,
    extract_league_info,
    parse_date,
    parse_score,
    read_games,
)


class TestParseDate:
    def test_valid_date(self):
        result = parse_date("15.01.2026 10:00")
        assert result == datetime(2026, 1, 15, 10, 0)

    def test_invalid_format(self):
        assert parse_date("2026-01-15") is None

    def test_none_input(self):
        assert parse_date(None) is None

    def test_whitespace(self):
        result = parse_date("  15.01.2026 10:00  ")
        assert result == datetime(2026, 1, 15, 10, 0)

    def test_empty_string(self):
        assert parse_date("") is None


class TestParseScore:
    def test_valid_score(self):
        assert parse_score("79 : 75") == (79, 75)

    def test_valid_score_no_spaces(self):
        assert parse_score("79:75") == (79, 75)

    def test_missing_score_empty(self):
        assert parse_score("") == (None, None)

    def test_missing_score_whitespace(self):
        assert parse_score("   ") == (None, None)

    def test_invalid_format(self):
        assert parse_score("abc") == (None, None)

    def test_none_input(self):
        assert parse_score(None) == (None, None)

    def test_non_numeric(self):
        assert parse_score("ab : cd") == (None, None)


class TestExtractLeagueInfo:
    def test_valid_ergebnisse_title(self):
        html = (
            "<html><head>"
            "<title>Ergebnisse - Test Bezirksliga (U12 ...)</title>"
            "</head></html>"
        )
        info = extract_league_info(html)
        assert info.name == "Test Bezirksliga"
        assert info.number is None

    def test_valid_spielplan_title(self):
        html = (
            "<html><head>"
            "<title>Spielplan - My League (Senior ...)</title>"
            "</head></html>"
        )
        info = extract_league_info(html)
        assert info.name == "My League"
        assert info.number is None

    def test_with_liganr(self):
        html = (
            "<td>Ergebnisse - MFR U12 mix Bezirksliga Nord "
            "(U12 Mittelfranken; Liganr.: 23182)</td>"
        )
        info = extract_league_info(html)
        assert info.name == "MFR U12 mix Bezirksliga Nord"
        assert info.number == 23182

    def test_missing_title(self):
        html = "<html><head><title>Some random title</title></head></html>"
        info = extract_league_info(html)
        assert info.name == "Basketball League"
        assert info.number is None

    def test_empty_html(self):
        info = extract_league_info("")
        assert info.name == "Basketball League"
        assert info.number is None

    def test_to_dict(self):
        info = LeagueInfo(name="Test League", number=12345)
        assert info.to_dict() == {
            "liga_name": "Test League",
            "liga_number": 12345,
        }

    def test_to_dict_no_number(self):
        info = LeagueInfo(name="Test League")
        assert info.to_dict() == {
            "liga_name": "Test League",
            "liga_number": None,
        }


class TestHTMLResultsParser:
    def test_row_parsing(self):
        parser = _HTMLResultsParser()
        parser.feed(
            "<tr><td>1</td><td>1</td><td>15.01.2026 10:00</td>"
            "<td>Team A</td><td>Team B</td><td>79 : 75</td></tr>"
        )
        assert len(parser.games) == 1
        g = parser.games[0]
        assert g.home == "Team A"
        assert g.away == "Team B"
        assert g.home_score == 79
        assert g.away_score == 75

    def test_cancelled_row_skipped(self):
        parser = _HTMLResultsParser()
        parser.feed(
            "<tr><td><STRIKE>1</STRIKE></td><td><STRIKE>1</STRIKE></td>"
            "<td><STRIKE>15.01.2026 10:00</STRIKE></td>"
            "<td><STRIKE>Team A</STRIKE></td><td><STRIKE>Team B</STRIKE></td>"
            "<td><STRIKE>0 : 20</STRIKE></td></tr>"
        )
        assert len(parser.games) == 0

    def test_incomplete_row_skipped(self):
        parser = _HTMLResultsParser()
        parser.feed("<tr><td>1</td><td>1</td></tr>")
        assert len(parser.games) == 0

    def test_row_with_missing_score_skipped(self):
        parser = _HTMLResultsParser()
        parser.feed(
            "<tr><td>1</td><td>1</td><td>15.01.2026 10:00</td>"
            "<td>Team A</td><td>Team B</td><td></td></tr>"
        )
        assert len(parser.games) == 0


class TestReadGames:
    def test_valid_games(self, ergebnisse_path):
        games, league_info = read_games(ergebnisse_path)
        assert league_info.name == "Test Bezirksliga"
        assert league_info.number == 99999
        assert len(games) == 4  # 5 rows, 1 cancelled

    def test_sorting_newest_first(self, ergebnisse_path):
        games, _ = read_games(ergebnisse_path)
        for i in range(len(games) - 1):
            assert games[i].date >= games[i + 1].date

    def test_cancelled_games_skipped(self, ergebnisse_path):
        games, _ = read_games(ergebnisse_path)
        # The cancelled game (Team Gamma vs Team Alpha) should not appear
        for g in games:
            assert not (g.home == "Team Gamma" and g.away == "Team Alpha")

    def test_missing_file_raises(self, tmp_path):
        import pytest

        with pytest.raises(SystemExit):
            read_games(str(tmp_path / "nonexistent.html"))
