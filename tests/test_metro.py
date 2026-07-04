from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from src.app import app
from src.models.metro import DireccionMetro, LlegadasMetro, ProximoMetro
from src.services import metro as metro_service
from src.services.metro_catalog import paradas as metro_paradas
from src.services.metro_store import InMemoryMetroSnapshotStore, MetroSnapshot

def _build_snapshot(*, fetched_at: datetime | None = None) -> MetroSnapshot:
    fetched_at = fetched_at or datetime.now(timezone.utc)
    arrivals = [
        LlegadasMetro(
            parada=next(parada for parada in metro_paradas if parada.id == "101"),
            proximos=[
                ProximoMetro(direccion=DireccionMetro.Albolote, minutos=1),
                ProximoMetro(direccion=DireccionMetro.Armilla, minutos=3),
            ],
        ),
        LlegadasMetro(
            parada=next(parada for parada in metro_paradas if parada.id == "105"),
            proximos=[ProximoMetro(direccion=DireccionMetro.Armilla, minutos=5)],
        ),
    ]
    return MetroSnapshot(fetched_at=fetched_at, arrivals=arrivals, source_latency_ms=120)


@pytest.fixture(autouse=True)
def metro_snapshot_store(monkeypatch: pytest.MonkeyPatch) -> InMemoryMetroSnapshotStore:
    store = InMemoryMetroSnapshotStore(_build_snapshot())
    monkeypatch.setattr(metro_service, "snapshot_store", store)
    monkeypatch.setenv("ALLOW_DIRECT_METRO_SCRAPE", "false")
    return store


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


def test_paradas(client: TestClient):
    response = client.get("/metro/paradas")
    assert response.status_code == 200  # noqa: PLR2004
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == len(metro_paradas)


def test_llegadas(client: TestClient, metro_snapshot_store: InMemoryMetroSnapshotStore):
    response = client.get("/metro/llegadas")
    assert response.status_code == 200  # noqa: PLR2004
    data = response.json()
    assert isinstance(data, list)
    assert all(LlegadasMetro.model_validate(item) for item in data)
    assert int(response.headers["x-movgr-data-age-seconds"]) >= 0
    assert "x-movgr-data-fetched-at" in response.headers


def test_llegadas_parada_not_found(client: TestClient):
    response = client.get("/metro/llegadas/NotALine")
    assert response.status_code == 404  # noqa: PLR2004


def test_llegadas_parada_found(client: TestClient):
    response = client.get("/metro/llegadas/105")
    assert response.status_code == 200  # noqa: PLR2004
    data = response.json()
    assert LlegadasMetro.model_validate(data)
    assert data["parada"]["id"] == "105"


def test_llegadas_returns_503_when_snapshot_missing(
    client: TestClient,
    metro_snapshot_store: InMemoryMetroSnapshotStore,
) -> None:
    metro_snapshot_store._snapshot = None

    response = client.get("/metro/llegadas")

    assert response.status_code == 503  # noqa: PLR2004


def test_llegadas_returns_503_when_snapshot_expired(
    client: TestClient,
    metro_snapshot_store: InMemoryMetroSnapshotStore,
) -> None:
    stale_snapshot = _build_snapshot(fetched_at=datetime.now(timezone.utc) - timedelta(minutes=6))
    metro_snapshot_store.put_current(stale_snapshot)

    response = client.get("/metro/llegadas")

    assert response.status_code == 503  # noqa: PLR2004
