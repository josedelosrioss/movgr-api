import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from src.services import metro_refresher
from src.services.metro_store import InMemoryMetroSnapshotStore, MetroSnapshot

STALE_AGE_SECONDS = 320  # beyond METRO_MAX_STALE_SECONDS=300 set below


class FakeWsManager:
    def __init__(self) -> None:
        self.messages: list[dict] = []

    async def broadcast(self, message: dict) -> None:
        self.messages.append(message)


def _snapshot(age_seconds: int) -> MetroSnapshot:
    return MetroSnapshot(
        fetched_at=datetime.now(timezone.utc) - timedelta(seconds=age_seconds),
        arrivals=[],
    )


def _failing_scrape() -> MetroSnapshot:
    raise RuntimeError("metropolitanogranada.es down")


@pytest.fixture(autouse=True)
def _max_stale_300(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("METRO_MAX_STALE_SECONDS", "300")


def test_successful_scrape_stores_and_broadcasts_snapshot(monkeypatch: pytest.MonkeyPatch) -> None:
    fresh = _snapshot(age_seconds=0)
    monkeypatch.setattr(metro_refresher, "fetch_llegadas_snapshot", lambda: fresh)
    store = InMemoryMetroSnapshotStore()
    ws = FakeWsManager()

    asyncio.run(metro_refresher.refresh_once(store, ws))

    assert store.get_current() is fresh
    assert [m["type"] for m in ws.messages] == ["snapshot"]


def test_failed_scrape_with_stale_snapshot_broadcasts_stale(monkeypatch: pytest.MonkeyPatch) -> None:
    old = _snapshot(age_seconds=STALE_AGE_SECONDS)
    monkeypatch.setattr(metro_refresher, "fetch_llegadas_snapshot", _failing_scrape)
    store = InMemoryMetroSnapshotStore(old)
    ws = FakeWsManager()

    asyncio.run(metro_refresher.refresh_once(store, ws))

    assert store.get_current() is old
    assert len(ws.messages) == 1
    message = ws.messages[0]
    assert message["type"] == "stale"
    assert message["fetched_at"] == old.fetched_at.isoformat()
    assert message["age_seconds"] >= STALE_AGE_SECONDS


def test_failed_scrape_with_fresh_snapshot_broadcasts_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(metro_refresher, "fetch_llegadas_snapshot", _failing_scrape)
    store = InMemoryMetroSnapshotStore(_snapshot(age_seconds=30))
    ws = FakeWsManager()

    asyncio.run(metro_refresher.refresh_once(store, ws))

    assert ws.messages == []


def test_failed_scrape_without_snapshot_broadcasts_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(metro_refresher, "fetch_llegadas_snapshot", _failing_scrape)
    ws = FakeWsManager()

    asyncio.run(metro_refresher.refresh_once(InMemoryMetroSnapshotStore(), ws))

    assert ws.messages == []
