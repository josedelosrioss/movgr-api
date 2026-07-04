import os
from datetime import datetime, timezone

from src.exceptions.exceptions import MetroDataUnavailableError, ParadaNotFoundError
from src.models.metro import LlegadasMetro
from src.services.metro_scraper import fetch_llegadas_snapshot
from src.services.metro_store import MetroSnapshot, MetroSnapshotStore, build_snapshot_store

snapshot_store = build_snapshot_store()


def set_snapshot_store(store: MetroSnapshotStore) -> None:
    """Point the REST layer at a specific store (shared with the background refresher)."""
    global snapshot_store  # noqa: PLW0603 - single shared process-wide store
    snapshot_store = store


def get_current_snapshot_or_none() -> MetroSnapshot | None:
    """Return the current snapshot without raising or enforcing staleness (used by the WS handler)."""
    if snapshot_store is None:
        return None
    return snapshot_store.get_current()


def _allow_direct_scrape() -> bool:
    return os.getenv("ALLOW_DIRECT_METRO_SCRAPE", "true").lower() == "true"


def _max_stale_seconds() -> int:
    return int(os.getenv("METRO_MAX_STALE_SECONDS", "300"))


def _snapshot_age_seconds(snapshot: MetroSnapshot) -> int:
    return max(0, int((datetime.now(timezone.utc) - snapshot.fetched_at).total_seconds()))


def get_llegadas_snapshot() -> MetroSnapshot:
    if snapshot_store is None:
        if not _allow_direct_scrape():
            raise MetroDataUnavailableError from None
        return fetch_llegadas_snapshot()

    snapshot = snapshot_store.get_current()
    if snapshot is None:
        raise MetroDataUnavailableError from None

    if _snapshot_age_seconds(snapshot) > _max_stale_seconds():
        raise MetroDataUnavailableError from None

    return snapshot


def get_snapshot_headers(snapshot: MetroSnapshot) -> dict[str, str]:
    return {
        "X-Movgr-Data-Fetched-At": snapshot.fetched_at.isoformat(),
        "X-Movgr-Data-Age-Seconds": str(_snapshot_age_seconds(snapshot)),
    }


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
