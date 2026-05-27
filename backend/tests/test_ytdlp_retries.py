from __future__ import annotations

from unittest.mock import patch

import pytest

from app.services import ytdlp


def test_is_transient_download_error_detects_ssl() -> None:
    assert ytdlp._is_transient_download_error(RuntimeError("[SSL: UNEXPECTED_EOF_WHILE_READING]"))


def test_download_audio_retries_transient_errors() -> None:
    calls = {"count": 0}

    def flaky_download(*_args: object, **_kwargs: object) -> str:
        calls["count"] += 1
        if calls["count"] < 2:
            raise RuntimeError("[SSL: UNEXPECTED_EOF_WHILE_READING]")
        return "/tmp/track.opus"

    with (
        patch.object(ytdlp, "time") as time_mock,
        patch.object(ytdlp, "_download_audio_once", side_effect=flaky_download),
    ):
        path = ytdlp.download_audio("https://example.com/track", "/tmp/%(ext)s")

    assert path == "/tmp/track.opus"
    assert calls["count"] == 2
    time_mock.sleep.assert_called_once()


def test_download_audio_does_not_retry_permanent_errors() -> None:
    with (
        patch.object(
            ytdlp,
            "_download_audio_once",
            side_effect=RuntimeError("video unavailable"),
        ),
        pytest.raises(RuntimeError, match="video unavailable"),
    ):
        ytdlp.download_audio("https://example.com/track", "/tmp/%(ext)s")
