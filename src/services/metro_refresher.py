import asyncio
import logging

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


async def refresh_loop(store: MetroSnapshotStore, ws_manager: WsManager) -> None:
    """Scrape metro arrivals on an interval, store them, and push to connected clients.

    Runs the blocking scrape in a worker thread so it never stalls the event loop.
    Scrapes every ``REFRESH_SECONDS`` while clients are connected and slows to
    ``IDLE_REFRESH_SECONDS`` when nobody is listening. A failed scrape is logged and the
    previous snapshot is kept.
    """
    while True:
        try:
            snapshot = await asyncio.to_thread(fetch_llegadas_snapshot)
            store.put_current(snapshot)
            await ws_manager.broadcast(snapshot_message(snapshot))
        except Exception:  # noqa: BLE001 - keep the loop alive across scrape failures
            LOGGER.exception("Metro scrape failed; keeping previous snapshot")

        delay = REFRESH_SECONDS if ws_manager.client_count > 0 else IDLE_REFRESH_SECONDS
        # Sleep for `delay`, but wake immediately if a client connects mid-idle so the
        # first client never waits out the full idle interval for a fresh push.
        await ws_manager.wait_for_activity_or(delay)
