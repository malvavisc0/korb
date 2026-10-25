"""Tests for anti-bot headers, response decompression, and download_league."""

import gzip
import urllib.error
import zlib
from unittest.mock import MagicMock, patch

import pytest

from korb.download import (
    DELAY_MAX,
    DELAY_MIN,
    HEADERS,
    discover_league_ids,
    download_league,
    read_response,
)


class TestHeaders:
    """Verify HEADERS looks like a real browser, not a bot."""

    def test_user_agent_is_browser_like(self):
        ua = HEADERS["User-Agent"]
        assert "Mozilla" in ua
        assert "Chrome" in ua
        assert "korb" not in ua

    def test_accept_language_is_german(self):
        assert "de-DE" in HEADERS["Accept-Language"]

    def test_sec_fetch_headers_present(self):
        for key in (
            "Sec-Fetch-Dest",
            "Sec-Fetch-Mode",
            "Sec-Fetch-Site",
            "Sec-Fetch-User",
        ):
            assert key in HEADERS, f"Missing header: {key}"

    def test_client_hints_present(self):
        assert "Sec-CH-UA" in HEADERS
        assert "Sec-CH-UA-Mobile" in HEADERS
        assert "Sec-CH-UA-Platform" in HEADERS

    def test_accept_encoding_present(self):
        ae = HEADERS["Accept-Encoding"]
        assert "gzip" in ae
        assert "deflate" in ae

    def test_referer_set(self):
        assert HEADERS["Referer"].startswith("https://www.basketball-bund.net")

    def test_dnt_set(self):
        assert HEADERS["DNT"] == "1"


def _valid_html(marker: str) -> bytes:
    return (
        f'<html><body><a href="index?viewDescKey={marker}&liga_id=12345">'
        "x</a></body></html>"
    ).encode()


def _fake_response(body: bytes, encoding: str = "") -> MagicMock:
    """Build a mock HTTP response with the given body & encoding."""
    resp = MagicMock()
    resp.read.return_value = body
    resp.headers = MagicMock()
    resp.headers.get.return_value = encoding
    return resp


class TestReadResponse:
    """Verify read_response decompresses correctly."""

    def test_plain_passthrough(self):
        raw = b"<html>hello</html>"
        resp = _fake_response(raw, "")
        assert read_response(resp) == raw

    def test_gzip_decompression(self):
        original = b"<html>gzip content</html>"
        compressed = gzip.compress(original)
        resp = _fake_response(compressed, "gzip")
        assert read_response(resp) == original

    def test_deflate_zlib_wrapped(self):
        original = b"<html>deflate zlib</html>"
        compressed = zlib.compress(original)
        resp = _fake_response(compressed, "deflate")
        assert read_response(resp) == original

    def test_deflate_raw(self):
        original = b"<html>deflate raw</html>"
        compressed = zlib.compress(original, level=6)
        # Strip the zlib header (first 2 bytes) and checksum (last 4)
        raw_deflate = compressed[2:-4]
        resp = _fake_response(raw_deflate, "deflate")
        assert read_response(resp) == original

    def test_unknown_encoding_passthrough(self):
        raw = b"something"
        resp = _fake_response(raw, "identity")
        assert read_response(resp) == raw


class TestDownload:
    """Verify download_league sends correct headers and sleeps between requests."""

    @patch("korb.download.time.sleep")
    @patch("korb.download.urllib.request.urlopen")
    def test_sends_browser_headers(self, mock_urlopen, _mock_sleep, tmp_path):
        """The Request objects must carry our anti-bot headers."""
        # Mock a minimal HTTP response
        mock_resp = MagicMock()
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_resp.read.side_effect = [
            _valid_html("ErgebnisseViewPublic"),
            _valid_html("SpielplanViewPublic"),
        ]
        mock_resp.headers = MagicMock()
        mock_resp.headers.get.return_value = ""
        mock_urlopen.return_value = mock_resp

        with patch("korb.download.Path") as mock_path_cls:
            # Wire up Path so dirs/files are created under tmp_path
            mock_root = MagicMock()
            mock_liga = MagicMock()
            mock_path_cls.return_value = mock_root
            mock_root.__truediv__ = MagicMock(return_value=mock_root)
            mock_root.mkdir = MagicMock()

            # Use real tmp_path for file writes
            dest_a = tmp_path / "ergebnisse.html"
            dest_b = tmp_path / "spielplan.html"
            mock_liga.__truediv__ = MagicMock(side_effect=[dest_a, dest_b])
            mock_root.__truediv__ = MagicMock(return_value=mock_liga)
            mock_liga.mkdir = MagicMock()

            download_league(12345)

        # Two requests made
        assert mock_urlopen.call_count == 2

        # Each Request carries the browser User-Agent
        for call in mock_urlopen.call_args_list:
            req = call[0][0]
            assert "Mozilla" in req.get_header("User-agent")

    @patch("korb.download.urllib.request.urlopen")
    @patch("korb.download.time.sleep")
    def test_sleeps_between_requests(self, mock_sleep, mock_urlopen, tmp_path):
        """There must be a delay between the two downloads."""
        mock_resp = MagicMock()
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_resp.read.side_effect = [
            _valid_html("ErgebnisseViewPublic"),
            _valid_html("SpielplanViewPublic"),
        ]
        mock_resp.headers = MagicMock()
        mock_resp.headers.get.return_value = ""
        mock_urlopen.return_value = mock_resp

        with patch("korb.download.Path") as mock_path_cls:
            mock_root = MagicMock()
            mock_liga = MagicMock()
            mock_path_cls.return_value = mock_root
            mock_root.mkdir = MagicMock()

            dest_a = tmp_path / "ergebnisse.html"
            dest_b = tmp_path / "spielplan.html"
            mock_liga.__truediv__ = MagicMock(side_effect=[dest_a, dest_b])
            mock_root.__truediv__ = MagicMock(return_value=mock_liga)
            mock_liga.mkdir = MagicMock()

            download_league(12345)

        # sleep called exactly once (between request 0 and 1)
        assert mock_sleep.call_count == 1
        delay = mock_sleep.call_args[0][0]
        assert DELAY_MIN <= delay <= DELAY_MAX


class TestDelayConstants:
    """Sanity-check the delay range constants."""

    def test_min_less_than_max(self):
        assert DELAY_MIN < DELAY_MAX

    def test_min_positive(self):
        assert DELAY_MIN > 0


class TestDiscoverLeagueIds:
    """Verify discover_league_ids scans the files/ directory."""

    def test_finds_numeric_dirs_with_html(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        # Create two league directories with HTML files
        for lid in (111, 222):
            d = tmp_path / "files" / str(lid)
            d.mkdir(parents=True)
            (d / "ergebnisse.html").write_text("<html></html>")
        assert discover_league_ids() == [111, 222]

    def test_ignores_non_numeric_dirs(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        d = tmp_path / "files" / "not_a_number"
        d.mkdir(parents=True)
        (d / "ergebnisse.html").write_text("<html></html>")
        assert discover_league_ids() == []

    def test_ignores_dirs_without_html(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        d = tmp_path / "files" / "555"
        d.mkdir(parents=True)
        (d / "readme.txt").write_text("no html here")
        assert discover_league_ids() == []

    def test_missing_files_dir(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        assert discover_league_ids() == []

    def test_sorted_output(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        for lid in [300, 100, 200]:
            d = tmp_path / "files" / str(lid)
            d.mkdir(parents=True)
            (d / "spielplan.html").write_text("<html></html>")
        assert discover_league_ids() == [100, 200, 300]

    def test_sorted_numerically_not_lexically(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        for lid in [100, 20, 3]:
            d = tmp_path / "files" / str(lid)
            d.mkdir(parents=True)
            (d / "ergebnisse.html").write_text("<html></html>")
        assert discover_league_ids() == [3, 20, 100]

    def test_ignores_gitkeep_and_files(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        files_dir = tmp_path / "files"
        files_dir.mkdir()
        (files_dir / ".gitkeep").write_text("")
        d = files_dir / "777"
        d.mkdir()
        (d / "ergebnisse.html").write_text("<html></html>")
        assert discover_league_ids() == [777]


class TestDownloadFailure:
    """Verify network errors fail clearly."""

    @patch(
        "korb.download.urllib.request.urlopen",
        side_effect=urllib.error.URLError("boom"),
    )
    def test_network_error_exits(self, mock_urlopen, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        with pytest.raises(SystemExit):
            download_league(12345)
        mock_urlopen.assert_called_once()

    @patch(
        "korb.download.urllib.request.urlopen",
        side_effect=TimeoutError("timed out"),
    )
    def test_timeout_exits(self, mock_urlopen, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        with pytest.raises(SystemExit):
            download_league(12345)
        mock_urlopen.assert_called_once()

    @patch("korb.download.urllib.request.urlopen")
    def test_empty_response_exits_without_writing(
        self, mock_urlopen, tmp_path, monkeypatch
    ):
        monkeypatch.chdir(tmp_path)
        mock_resp = MagicMock()
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_resp.read.return_value = b"  \n"
        mock_resp.headers.get.return_value = ""
        mock_urlopen.return_value = mock_resp

        with pytest.raises(SystemExit):
            download_league(12345)

        assert not (tmp_path / "files" / "12345" / "ergebnisse.html").exists()

    @patch("korb.download.urllib.request.urlopen")
    def test_unexpected_page_exits_without_writing(
        self, mock_urlopen, tmp_path, monkeypatch
    ):
        monkeypatch.chdir(tmp_path)
        mock_resp = MagicMock()
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_resp.read.return_value = b"<html><head><title>Login</title></head></html>"
        mock_resp.headers.get.return_value = ""
        mock_urlopen.return_value = mock_resp

        with pytest.raises(SystemExit):
            download_league(12345)

        assert not (tmp_path / "files" / "12345" / "ergebnisse.html").exists()


class TestCmdDownloadAll:
    """Verify download --all behaviour."""

    @patch("korb.__main__.wait_between_requests")
    @patch("korb.__main__.download_league")
    @patch("korb.__main__.discover_league_ids", return_value=[100, 200])
    def test_downloads_all_discovered(
        self,
        _mock_discover,
        mock_download,
        _mock_wait,
        capsys,
    ):
        from korb.__main__ import cmd_download

        args = MagicMock()
        args.all = True
        args.ligaid = None
        cmd_download(args)

        assert mock_download.call_count == 2
        mock_download.assert_any_call(100)
        mock_download.assert_any_call(200)
        out = capsys.readouterr().out
        assert "2 league(s)" in out
        assert "Done." in out

    @patch("korb.__main__.discover_league_ids", return_value=[])
    def test_no_leagues_found(self, _mock_discover):
        from korb.__main__ import cmd_download

        args = MagicMock()
        args.all = True
        args.ligaid = None
        with pytest.raises(SystemExit):
            cmd_download(args)

    @patch("korb.__main__.download_league")
    def test_ligaid_overrides_all(self, mock_download):
        """When --ligaid is given, --all is ignored."""
        from korb.__main__ import cmd_download

        args = MagicMock()
        args.all = True
        args.ligaid = 999
        cmd_download(args)

        mock_download.assert_called_once_with(999)

    def test_requires_ligaid(self):
        from korb.__main__ import cmd_download

        args = MagicMock()
        args.all = False
        args.ligaid = None
        with pytest.raises(SystemExit):
            cmd_download(args)
