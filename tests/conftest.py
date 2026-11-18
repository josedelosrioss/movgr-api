import pytest


@pytest.fixture(autouse=True)
def _disable_metro_refresher(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep the background scraper loop off during tests.

    With it disabled the app lifespan neither hits the network nor replaces the
    snapshot store that individual tests inject via monkeypatch.
    """
    monkeypatch.setenv("METRO_REFRESHER_ENABLED", "false")
