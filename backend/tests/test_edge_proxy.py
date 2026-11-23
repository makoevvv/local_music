from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_caddyfile_serves_the_spa_and_proxies_the_api() -> None:
    text = (ROOT / "infra" / "Caddyfile").read_text()
    assert "reverse_proxy backend:8000" in text
    assert "Strict-Transport-Security" in text
    assert "root * /srv/web" in text
    assert "try_files {path} /index.html" in text
    assert "tls internal" in text


def test_edge_profile_runs_caddy_and_cloudflared() -> None:
    text = (ROOT / "infra" / "docker-compose.yml").read_text()
    assert "profiles: [\"edge\"]" in text
    assert "dockerfile: web/Dockerfile" in text
    assert "cloudflare/cloudflared:2025.11.1" in text
    assert "CLOUDFLARE_TUNNEL_TOKEN" in text
    example = (ROOT / "infra" / "cloudflared" / "config.yml.example").read_text()
    assert "http://caddy:80" in example
