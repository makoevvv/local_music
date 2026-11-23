from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

from app.core.logging import JsonFormatter, build_log_config, configure_logging, resolve_level

ROOT = Path(__file__).resolve().parents[2]


def test_json_formatter_emits_one_object_per_record() -> None:
    record = logging.LogRecord(
        name="app.demo",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="hello %s",
        args=("world",),
        exc_info=None,
    )
    payload = json.loads(JsonFormatter().format(record))
    assert payload["level"] == "INFO"
    assert payload["logger"] == "app.demo"
    assert payload["message"] == "hello world"
    assert "ts" in payload
    assert set(payload) == {"ts", "level", "logger", "message"}


def test_json_formatter_includes_exception_text() -> None:
    try:
        raise RuntimeError("boom")
    except RuntimeError:
        record = logging.LogRecord(
            name="app.demo",
            level=logging.ERROR,
            pathname=__file__,
            lineno=1,
            msg="failed",
            args=(),
            exc_info=sys.exc_info(),
        )
    payload = json.loads(JsonFormatter().format(record))
    assert "RuntimeError: boom" in payload["exception"]


def test_unknown_level_falls_back_to_info() -> None:
    assert resolve_level("nope") == "INFO"
    assert resolve_level("debug") == "DEBUG"


def test_configure_logging_hides_debug_when_level_is_info(capsys: object) -> None:
    root = logging.getLogger()
    previous_handlers = root.handlers[:]
    previous_level = root.level
    try:
        configure_logging("INFO")
        logging.getLogger("app.demo").debug("hidden")
        logging.getLogger("app.demo").info("shown")
        lines = [line for line in capsys.readouterr().out.splitlines() if line]  # type: ignore[attr-defined]
        assert len(lines) == 1
        payload = json.loads(lines[0])
        assert payload["message"] == "shown"
        assert payload["level"] == "INFO"
    finally:
        root.handlers = previous_handlers
        root.setLevel(previous_level)


def test_api_entrypoint_uses_the_json_log_config(monkeypatch: object) -> None:
    captured: dict[str, object] = {}

    def fake_run(*_args: object, **kwargs: object) -> None:
        captured.update(kwargs)

    monkeypatch.setattr("uvicorn.run", fake_run)  # type: ignore[attr-defined]
    from app.main import main

    main()
    config = captured["log_config"]
    assert isinstance(config, dict)
    assert config["formatters"]["json"]["()"] == "app.core.logging.JsonFormatter"
    assert config["root"]["level"] == resolve_level("INFO")


def test_worker_entrypoint_emits_json(monkeypatch: object, capsys: object) -> None:
    def fake_rq() -> None:
        logging.getLogger("rq.worker").info("worker-ready")

    monkeypatch.setattr("rq.cli.cli.main", fake_rq)  # type: ignore[attr-defined]
    from app.workers.__main__ import main

    root = logging.getLogger()
    previous_handlers = root.handlers[:]
    previous_level = root.level
    try:
        main()
        lines = [line for line in capsys.readouterr().out.splitlines() if line]  # type: ignore[attr-defined]
        payload = json.loads(lines[-1])
        assert payload["message"] == "worker-ready"
        assert payload["logger"] == "rq.worker"
    finally:
        root.handlers = previous_handlers
        root.setLevel(previous_level)


def test_compose_starts_api_and_worker_with_json_logging() -> None:
    dockerfile = (ROOT / "backend" / "Dockerfile").read_text()
    compose = (ROOT / "infra" / "docker-compose.yml").read_text()
    assert 'CMD ["python", "-m", "app.main"]' in dockerfile
    assert '"app.workers"' in compose
    assert '"worker"' in compose
    assert build_log_config("DEBUG")["root"]["level"] == "DEBUG"
