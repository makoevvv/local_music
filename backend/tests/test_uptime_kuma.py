from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_uptime_kuma_is_a_loopback_monitor() -> None:
    text = (ROOT / "infra" / "docker-compose.yml").read_text()
    service, volumes = text.split("\nvolumes:\n", 1)
    kuma = service.split("uptime-kuma:", 1)[1]
    assert "image: louislam/uptime-kuma:2.5.12" in kuma
    assert 'profiles: ["monitor"]' in kuma
    assert "restart: unless-stopped" in kuma
    assert '"127.0.0.1:3001:3001"' in kuma
    assert "uptime_kuma:/app/data" in kuma
    assert "\n      - backend\n" in kuma
    assert "\n  uptime_kuma:\n" in volumes or volumes.strip().endswith("uptime_kuma:")
