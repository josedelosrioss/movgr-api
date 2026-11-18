from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from src.app import app
from src.models.metro import DireccionMetro, LlegadasMetro, ProximoMetro
from src.services import metro as metro_service
from src.services.metro_catalog import paradas as metro_paradas
from src.services.metro_store import InMemoryMetroSnapshotStore, MetroSnapshot

FIRST_ARRIVAL_MINUTES = 2


def _build_snapshot() -> MetroSnapshot:
    arrivals = [
        LlegadasMetro(
            parada=next(parada for parada in metro_paradas if parada.id == "101"),
            proximos=[ProximoMetro(direccion=DireccionMetro.Albolote, minutos=FIRST_ARRIVAL_MINUTES)],
        ),
    ]
    return MetroSnapshot(
        fetched_at=datetime.now(timezone.utc),
        arrivals=arrivals,
        source_latency_ms=100,
    )


@pytest.fixture
def seeded_store(monkeypatch: pytest.MonkeyPatch) -> InMemoryMetroSnapshotStore:
    store = InMemoryMetroSnapshotStore(_build_snapshot())
    monkeypatch.setattr(metro_service, "snapshot_store", store)
    return store


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


def test_ws_sends_snapshot_on_connect(
    client: TestClient,
    seeded_store: InMemoryMetroSnapshotStore,
) -> None:
    with client.websocket_connect("/ws/metro") as websocket:
        message = websocket.receive_json()

    assert message["type"] == "snapshot"
    assert "fetched_at" in message
    assert message["arrivals"][0]["parada"]["id"] == "101"
    assert message["arrivals"][0]["proximos"][0]["minutos"] == FIRST_ARRIVAL_MINUTES


def test_ws_connects_without_snapshot(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(metro_service, "snapshot_store", InMemoryMetroSnapshotStore())

    with client.websocket_connect("/ws/metro") as websocket:
        # No snapshot available yet: the connection stays open and simply sends nothing.
        websocket.send_text("ping")


def test_ws_sends_stale_after_snapshot_when_data_is_old(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stale_age_seconds = 400
    monkeypatch.setenv("METRO_MAX_STALE_SECONDS", "300")
    old = _build_snapshot().model_copy(
        update={"fetched_at": datetime.now(timezone.utc) - timedelta(seconds=stale_age_seconds)},
    )
    monkeypatch.setattr(metro_service, "snapshot_store", InMemoryMetroSnapshotStore(old))

    with client.websocket_connect("/ws/metro") as websocket:
        first = websocket.receive_json()
        second = websocket.receive_json()

    assert first["type"] == "snapshot"
    assert second["type"] == "stale"
    assert second["fetched_at"] == old.fetched_at.isoformat()
    assert second["age_seconds"] >= stale_age_seconds
