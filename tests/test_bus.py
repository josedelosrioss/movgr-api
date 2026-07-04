import pytest
from fastapi.testclient import TestClient

from src.app import app
from src.models.bus import LlegadasBus, ParadaBus
from src.services import bus as bus_service

BUS_HTML = """
<div class="mainhead">
  <div style="color: #fff">Parada 249 - Camino de Ronda 1</div>
</div>
<div class="tf">
  <div class="tfr">
    <div class="tfcc"><div class="form_white">4</div></div>
    <div class="tfcc">6</div>
    <div class="tfcc">-</div>
    <div class="tfccs">Zaidín</div>
  </div>
</div>
"""

BUS_NOT_FOUND_HTML = """
<div class="message">La parada solicitada no existe</div>
"""


class FakeResponse:
    def __init__(self, text: str, status_code: int = 200) -> None:
        self.text = text
        self.status_code = status_code
        self.encoding = "utf-8"


@pytest.fixture(autouse=True)
def stub_bus_requests(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_perform_request(num_parada: int) -> FakeResponse:
        if num_parada == 249:  # noqa: PLR2004
            return FakeResponse(BUS_HTML)
        return FakeResponse(BUS_NOT_FOUND_HTML)

    monkeypatch.setattr(bus_service, "__perform_request", fake_perform_request)


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


def test_parada_not_found(client: TestClient):
    response = client.get("/bus/parada/230")
    assert response.status_code == 404  # noqa: PLR2004


def test_parada_found(client: TestClient):
    response = client.get("/bus/parada/249")
    assert response.status_code == 200  # noqa: PLR2004
    assert ParadaBus.model_validate(response.json())


def test_llegadas_not_found(client: TestClient):
    response = client.get("/bus/llegadas/230")
    assert response.status_code == 404  # noqa: PLR2004


def test_llegadas_found(client: TestClient):
    response = client.get("/bus/llegadas/249")
    assert response.status_code == 200  # noqa: PLR2004
    data = response.json()
    assert LlegadasBus.model_validate(data)
    assert data["proximos"][0]["linea"]["id"] == "4"
