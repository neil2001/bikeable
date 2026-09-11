import pytest
from app.config import settings


@pytest.fixture(autouse=True)
def disable_live_elevation_lookups(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep routing tests offline; individual tests can opt back in."""
    monkeypatch.setattr(settings, "elevation_provider", "none")
