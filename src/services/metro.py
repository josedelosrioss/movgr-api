import os
from datetime import datetime, timezone

from src.exceptions.exceptions import MetroDataUnavailableError, ParadaNotFoundError
from src.models.metro import EstadoServicioMetro, LlegadasMetro
from src.services.metro_scraper import fetch_llegadas_snapshot
from src.services.metro_status import InMemoryServiceStatusStore, fetch_service_status_text, next_status
from src.services.metro_store import MetroSnapshot, MetroSnapshotStore, build_snapshot_store

snapshot_store = build_snapshot_store()
status_store: InMemoryServiceStatusStore | None = None


def set_snapshot_store(store: MetroSnapshotStore) -> None:
    """Point the REST layer at a specific store (shared with the background refresher)."""
    global snapshot_store  # noqa: PLW0603 - single shared process-wide store
    snapshot_store = store


def set_status_store(store: InMemoryServiceStatusStore) -> None:
    """Point the REST layer at the store filled by the background status refresher."""
    global status_store  # noqa: PLW0603 - single shared process-wide store
    status_store = store


def get_current_snapshot_or_none() -> MetroSnapshot | None:
    """Return the current snapshot without raising or enforcing staleness (used by the WS handler)."""
    if snapshot_store is None:
        return None
    return snapshot_store.get_current()


def _allow_direct_scrape() -> bool:
    return os.getenv("ALLOW_DIRECT_METRO_SCRAPE", "true").lower() == "true"


def _max_stale_seconds() -> int:
    return int(os.getenv("METRO_MAX_STALE_SECONDS", "300"))


def age_seconds(moment: datetime) -> int:
    return max(0, int((datetime.now(timezone.utc) - moment).total_seconds()))


def snapshot_age_seconds(snapshot: MetroSnapshot) -> int:
    return age_seconds(snapshot.fetched_at)


def is_stale(snapshot: MetroSnapshot) -> bool:
    """True when the snapshot is older than ``METRO_MAX_STALE_SECONDS`` (REST and WS share this rule)."""
    return snapshot_age_seconds(snapshot) > _max_stale_seconds()


def get_llegadas_snapshot() -> MetroSnapshot:
    if snapshot_store is None:
        if not _allow_direct_scrape():
            raise MetroDataUnavailableError from None
        return fetch_llegadas_snapshot()

    snapshot = snapshot_store.get_current()
    if snapshot is None:
        raise MetroDataUnavailableError from None

    if is_stale(snapshot):
        raise MetroDataUnavailableError from None

    return snapshot


def get_data_headers(fetched_at: datetime) -> dict[str, str]:
    return {
        "X-Movgr-Data-Fetched-At": fetched_at.isoformat(),
        "X-Movgr-Data-Age-Seconds": str(age_seconds(fetched_at)),
    }


def get_snapshot_headers(snapshot: MetroSnapshot) -> dict[str, str]:
    return get_data_headers(snapshot.fetched_at)


def get_service_status() -> EstadoServicioMetro:
    """Current service status; 503 (``MetroDataUnavailableError``) when missing or stale,
    so consumers never act on an outdated "normal".
    """
    if status_store is None:
        if not _allow_direct_scrape():
            raise MetroDataUnavailableError from None
        return next_status(None, fetch_service_status_text(), datetime.now(timezone.utc))

    status = status_store.get_current()
    if status is None or age_seconds(status.actualizado) > _max_stale_seconds():
        raise MetroDataUnavailableError from None
    return status


def get_llegadas() -> list[LlegadasMetro]:
    return get_llegadas_snapshot().arrivals


def get_llegadas_parada(
    id_parada: str,
    snapshot: MetroSnapshot | None = None,
) -> LlegadasMetro:
    current_snapshot = snapshot or get_llegadas_snapshot()
    for proximo in current_snapshot.arrivals:
        if proximo.parada.id == id_parada:
            return proximo
    raise ParadaNotFoundError from None
