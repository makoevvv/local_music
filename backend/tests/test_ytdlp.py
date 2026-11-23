from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from app.core.config import settings
from app.services.ytdlp import _ytdlp_base_opts


def test_ytdlp_base_opts_without_proxy() -> None:
    with patch.object(settings, "ytdlp_proxy", None):
        opts = _ytdlp_base_opts()
    assert "proxy" not in opts
    assert opts["extractor_args"]["youtubepot-bgutilhttp"]["base_url"] == settings.ytdlp_pot_base_url


def test_ytdlp_base_opts_with_proxy() -> None:
    with patch.object(settings, "ytdlp_proxy", "socks5h://proxy:1080"):
        opts = _ytdlp_base_opts()
    assert opts["proxy"] == "socks5h://proxy:1080"


def test_ytdlp_base_opts_with_cookies_file(tmp_path: Path) -> None:
    cookies = tmp_path / "cookies.txt"
    cookies.write_text("# Netscape HTTP Cookie File\n", encoding="utf-8")
    with patch.object(settings, "ytdlp_cookies_file", str(cookies)):
        opts = _ytdlp_base_opts()
    assert opts["cookiefile"] == str(cookies)
