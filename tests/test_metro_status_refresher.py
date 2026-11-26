import asyncio
import logging
from datetime import datetime, timedelta, timezone

import pytest
from src.services import metro_status_refresher
from src.services.metro_status import InMemoryServiceStatusStore, next_status

INCIDENT = "Servicio interrumpido en Armilla"


def _failing_fetch() -> str:
    raise RuntimeError("metropolitanogranada.es down")


def test_first_read_stores_status_and_logs_it(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(metro_status_refresher, "fetch_service_status_text", lambda: "Servicio sin incidencias")
    store = InMemoryServiceStatusStore()

    with caplog.at_level(logging.WARNING):
        asyncio.run(metro_status_refresher.refresh_status_once(store))

    status = store.get_current()
    assert status is not None
    assert status.normal is True
    assert "Metro service status changed" in caplog.text


def test_same_text_keeps_since_and_does_not_log(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    since = datetime.now(timezone.utc) - timedelta(minutes=10)
    store = InMemoryServiceStatusStore(next_status(None, INCIDENT, since))
    monkeypatch.setattr(metro_status_refresher, "fetch_service_status_text", lambda: INCIDENT)

    with caplog.at_level(logging.WARNING):
        asyncio.run(metro_status_refresher.refresh_status_once(store))

    status = store.get_current()
    assert status.desde == since
    assert status.actualizado > since
    assert "Metro service status changed" not in caplog.text


def test_changed_text_logs_old_and_new(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    store = InMemoryServiceStatusStore(next_status(None, "Servicio sin incidencias", datetime.now(timezone.utc)))
    monkeypatch.setattr(metro_status_refresher, "fetch_service_status_text", lambda: INCIDENT)

    with caplog.at_level(logging.WARNING):
        asyncio.run(metro_status_refresher.refresh_status_once(store))

    assert store.get_current().texto == INCIDENT
    assert "Servicio sin incidencias" in caplog.text
    assert INCIDENT in caplog.text


def test_failed_fetch_keeps_previous_status(monkeypatch: pytest.MonkeyPatch) -> None:
    previous = next_status(None, INCIDENT, datetime.now(timezone.utc))
    store = InMemoryServiceStatusStore(previous)
    monkeypatch.setattr(metro_status_refresher, "fetch_service_status_text", _failing_fetch)

    asyncio.run(metro_status_refresher.refresh_status_once(store))

    assert store.get_current() is previous


@pytest.mark.parametrize(("configured", "expected"), [(None, 20), ("30", 30), ("1", 5), ("abc", 20)])
def test_refresh_interval_from_environment(
    monkeypatch: pytest.MonkeyPatch, configured: str | None, expected: int
) -> None:
    if configured is None:
        monkeypatch.delenv("METRO_STATUS_REFRESH_SECONDS", raising=False)
    else:
        monkeypatch.setenv("METRO_STATUS_REFRESH_SECONDS", configured)

    assert metro_status_refresher.refresh_interval_seconds() == expected
