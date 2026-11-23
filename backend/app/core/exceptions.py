from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(HTTPException)
    async def http_exception_handler(_request: Request, exc: HTTPException) -> JSONResponse:
        detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
        body: dict[str, Any] = {
            "type": "about:blank",
            "title": detail,
            "status": exc.status_code,
            "detail": detail,
        }
        return JSONResponse(
            status_code=exc.status_code, content=body, media_type="application/problem+json"
        )
