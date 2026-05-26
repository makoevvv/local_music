from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.health import router


def test_health_returns_ok() -> None:
    app = FastAPI()
    app.include_router(router)

    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
