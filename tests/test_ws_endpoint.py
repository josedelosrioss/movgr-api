from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from src.app import app
from src.models.metro import DireccionMetro, LlegadasMetro, ProximoMetro
from src.services import metro as metro_service
from src.services.metro_catalog import paradas as metro_paradas
from src.services.metro_store import InMemoryMetroSnapshotStore, MetroSnapshot


def _build_snapshot() -> MetroSnapshot:
    arrivals = [
        LlegadasMetro(
            parada=next(parada for parada in metro_paradas if parada.id == "101"),
            proximos=[ProximoMetro(direccion=DireccionMetro.Albolote, minutos=2)],
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
    assert message["arrivals"][0]["proximos"][0]["minutos"] == 2


def test_ws_connects_without_snapshot(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(metro_service, "snapshot_store", InMemoryMetroSnapshotStore())

    with client.websocket_connect("/ws/metro") as websocket:
        # No snapshot available yet: the connection stays open and simply sends nothing.
        websocket.send_text("ping")
