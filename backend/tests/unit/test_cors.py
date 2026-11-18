"""The browser app (another origin) may call the API; other sites may not."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import CorsSettings
from app.main import app

PREFLIGHT = {
    "Access-Control-Request-Method": "POST",
    "Access-Control-Request-Headers": "content-type",
}


async def preflight(origin: str) -> dict[str, str]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.options("/health", headers={"Origin": origin, **PREFLIGHT})
    return dict(response.headers)


async def test_frontend_origin_is_allowed_by_default() -> None:
    headers = await preflight("http://localhost:3000")

    assert headers["access-control-allow-origin"] == "http://localhost:3000"


async def test_other_origins_are_not_allowed() -> None:
    headers = await preflight("https://evil.example")

    assert "access-control-allow-origin" not in headers


def test_cors_origins_are_a_comma_separated_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:3000, https://paper-rag.vercel.app")

    settings = CorsSettings(_env_file=None)  # type: ignore[call-arg]

    assert settings.origins == ["http://localhost:3000", "https://paper-rag.vercel.app"]
