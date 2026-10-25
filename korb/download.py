"""Download DBB league HTML from basketball-bund.net."""

import gzip
import http.client
import random
import sys
import time
import urllib.error
import urllib.request
import zlib
from pathlib import Path
from typing import Final

BASE = "https://www.basketball-bund.net/public"
RESULTS_URL = (
    f"{BASE}/ergebnisse.jsp?print=1"
    "&viewDescKey=sport.dbb.liga.ErgebnisseViewPublic"
    "/index.jsp_&liga_id={liga_id}"
)
SCHEDULE_URL = (
    f"{BASE}/spielplan_list.jsp?print=1"
    "&viewDescKey=sport.dbb.liga.SpielplanViewPublic"
    "/index.jsp_&liga_id={liga_id}"
)

HEADERS: Final[dict[str, str]] = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;"
        "q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8"
    ),
    "Accept-Language": "de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Sec-CH-UA": '"Chromium";v="131", "Not_A Brand";v="24"',
    "Sec-CH-UA-Mobile": "?0",
    "Sec-CH-UA-Platform": '"Windows"',
    "DNT": "1",
    "Referer": "https://www.basketball-bund.net/",
}

DELAY_MIN: Final[float] = 1.0
DELAY_MAX: Final[float] = 3.0
TIMEOUT_S: Final[float] = 30.0


def wait_between_requests() -> None:
    """Pause between consecutive requests to avoid rate-limiters."""
    time.sleep(random.uniform(DELAY_MIN, DELAY_MAX))


def read_response(resp: http.client.HTTPResponse) -> bytes:
    """Read and decompress an HTTP response body.

    Handles ``gzip`` and ``deflate`` Content-Encoding transparently so
    the caller always receives raw bytes.
    """
    raw = resp.read()
    encoding = resp.headers.get("Content-Encoding", "").strip().lower()
    if encoding == "gzip":
        return gzip.decompress(raw)
    if encoding == "deflate":
        # deflate may be raw-deflate or zlib-wrapped; try both.
        try:
            return zlib.decompress(raw)
        except zlib.error:
            return zlib.decompress(raw, -zlib.MAX_WBITS)
    return raw


def _is_expected_page(data: bytes, marker: str, ligaid: int) -> bool:
    """Return True if the HTML belongs to the expected league page."""
    text = data.decode("utf-8", errors="replace")
    return marker in text and f"liga_id={ligaid}" in text


def download_league(ligaid: int) -> None:
    """Download results and schedule HTML for a league.

    Args:
        ligaid: Liga ID on basketball-bund.net.
    """
    out_root = Path("files")
    out_root.mkdir(exist_ok=True)
    out = out_root / str(ligaid)
    out.mkdir(exist_ok=True)
    targets = [
        (
            RESULTS_URL.format(liga_id=ligaid),
            out / "ergebnisse.html",
            "ErgebnisseViewPublic",
        ),
        (
            SCHEDULE_URL.format(liga_id=ligaid),
            out / "spielplan.html",
            "SpielplanViewPublic",
        ),
    ]
    for i, (url, dest, marker) in enumerate(targets):
        if i > 0:
            wait_between_requests()
        print(
            f"Downloading {dest.name} ...",
            end=" ",
            flush=True,
        )
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
                data = read_response(resp)
                if not data.strip():
                    print("FAILED: empty response", file=sys.stderr)
                    sys.exit(1)
                if not _is_expected_page(data, marker, ligaid):
                    print(
                        f"FAILED: unexpected response (no {marker})",
                        file=sys.stderr,
                    )
                    sys.exit(1)
                _ = dest.write_bytes(data)
            print("OK")
        except (urllib.error.URLError, TimeoutError) as e:
            print(f"FAILED: {e}", file=sys.stderr)
            sys.exit(1)


def discover_league_ids() -> list[int]:
    """Scan the ``files/`` directory for downloaded league IDs.

    Looks for subdirectories whose names are valid integers and that
    contain at least one ``.html`` file.

    Returns:
        Sorted list of league IDs (int).
    """
    root = Path("files")
    if not root.is_dir():
        return []
    return sorted(
        int(entry.name)
        for entry in root.iterdir()
        if entry.is_dir() and entry.name.isdigit() and any(entry.glob("*.html"))
    )
