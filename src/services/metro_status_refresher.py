import asyncio
import logging
import os
from datetime import datetime, timezone

from src.services.metro_status import InMemoryServiceStatusStore, fetch_service_status_text, next_status

LOGGER = logging.getLogger(__name__)

DEFAULT_STATUS_REFRESH_SECONDS = 20
MIN_STATUS_REFRESH_SECONDS = 5


def refresh_interval_seconds() -> int:
    """``METRO_STATUS_REFRESH_SECONDS`` (default 20, minimum 5).

    A steady interval, not tied to WebSocket clients like the arrivals loop: incident
    detection must stay timely even when nobody has the app open.
    """
    try:
        configured = int(os.getenv("METRO_STATUS_REFRESH_SECONDS", str(DEFAULT_STATUS_REFRESH_SECONDS)))
    except ValueError:
        return DEFAULT_STATUS_REFRESH_SECONDS
    return max(MIN_STATUS_REFRESH_SECONDS, configured)


async def refresh_status_once(store: InMemoryServiceStatusStore) -> None:
    """Fetch the status once; keep the previous one if the fetch fails."""
    try:
        text = await asyncio.to_thread(fetch_service_status_text)
    except Exception:  # noqa: BLE001 - keep the loop alive across fetch failures
        LOGGER.exception("Metro service status fetch failed; keeping previous status")
        return

    previous = store.get_current()
    status = next_status(previous, text, datetime.now(timezone.utc))
    if previous is None or previous.texto != status.texto:
        # Logged at WARNING on purpose: this is how we learn the exact incident texts.
        LOGGER.warning(
            "Metro service status changed: %r -> %r",
            previous.texto if previous else None,
            status.texto,
        )
    store.put_current(status)


async def status_refresh_loop(store: InMemoryServiceStatusStore) -> None:
    while True:
        try:
            await refresh_status_once(store)
        except Exception:  # noqa: BLE001 - never let one bad iteration kill the loop
            LOGGER.exception("Metro service status iteration failed")
        await asyncio.sleep(refresh_interval_seconds())
