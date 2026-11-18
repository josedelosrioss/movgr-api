import asyncio
import logging

from src.services import metro as metro_service
from src.services.metro_scraper import fetch_llegadas_snapshot
from src.services.metro_store import MetroSnapshot, MetroSnapshotStore
from src.services.ws_manager import WsManager

LOGGER = logging.getLogger(__name__)

REFRESH_SECONDS = 15
IDLE_REFRESH_SECONDS = 120


def snapshot_message(snapshot: MetroSnapshot) -> dict:
    """Build the WebSocket payload for a snapshot (same shape as GET /metro/llegadas)."""
    return {
        "type": "snapshot",
        "fetched_at": snapshot.fetched_at.isoformat(),
        "arrivals": [arrival.model_dump(mode="json") for arrival in snapshot.arrivals],
    }


def stale_message(snapshot: MetroSnapshot) -> dict:
    """Build the WebSocket payload telling clients the last snapshot is too old to trust."""
    return {
        "type": "stale",
        "fetched_at": snapshot.fetched_at.isoformat(),
        "age_seconds": metro_service.snapshot_age_seconds(snapshot),
    }


async def refresh_once(store: MetroSnapshotStore, ws_manager: WsManager) -> None:
    """Scrape once; push the new snapshot, or a ``stale`` notice if scraping fails for too long.

    Runs the blocking scrape in a worker thread so it never stalls the event loop. A failed
    scrape keeps the previous snapshot; once that snapshot is older than
    ``METRO_MAX_STALE_SECONDS`` (the same rule REST uses to start returning errors), clients
    are told it is stale on every failed attempt until a scrape succeeds again.
    """
    try:
        snapshot = await asyncio.to_thread(fetch_llegadas_snapshot)
    except Exception:  # noqa: BLE001 - keep the loop alive across scrape failures
        LOGGER.exception("Metro scrape failed; keeping previous snapshot")
        previous = store.get_current()
        if previous is not None and metro_service.is_stale(previous):
            await ws_manager.broadcast(stale_message(previous))
        return

    store.put_current(snapshot)
    await ws_manager.broadcast(snapshot_message(snapshot))


async def refresh_loop(store: MetroSnapshotStore, ws_manager: WsManager) -> None:
    """Run ``refresh_once`` forever, every ``REFRESH_SECONDS`` while clients are connected
    and every ``IDLE_REFRESH_SECONDS`` when nobody is listening.
    """
    while True:
        try:
            await refresh_once(store, ws_manager)
        except Exception:  # noqa: BLE001 - never let one bad iteration kill the loop
            LOGGER.exception("Metro refresh iteration failed")

        delay = REFRESH_SECONDS if ws_manager.client_count > 0 else IDLE_REFRESH_SECONDS
        # Sleep for `delay`, but wake immediately if a client connects mid-idle so the
        # first client never waits out the full idle interval for a fresh push.
        await ws_manager.wait_for_activity_or(delay)
