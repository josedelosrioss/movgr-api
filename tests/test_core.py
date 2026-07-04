import pytest
from fastapi.testclient import TestClient

from src.app import app


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


def test_health_check(client: TestClient):
    response = client.get("/")
    assert response.status_code == 200  # noqa: PLR2004
