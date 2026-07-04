import asyncio
import logging

from fastapi import WebSocket

LOGGER = logging.getLogger(__name__)


class WsManager:
    """Tracks connected metro WebSocket clients and broadcasts snapshots to them."""

    def __init__(self) -> None:
        self._clients: set[WebSocket] = set()
        self._lock = asyncio.Lock()
        self._activity = asyncio.Event()

    @property
    def client_count(self) -> int:
        return len(self._clients)

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._clients.add(websocket)
        # Wake the refresher so it leaves the idle interval and tightens its cadence now.
        self._activity.set()

    async def wait_for_activity_or(self, timeout: float) -> None:
        """Sleep up to ``timeout`` seconds, returning early as soon as a client connects."""
        try:
            await asyncio.wait_for(self._activity.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            pass
        finally:
            self._activity.clear()

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            self._clients.discard(websocket)

    async def broadcast(self, message: dict) -> None:
        async with self._lock:
            clients = list(self._clients)

        for websocket in clients:
            try:
                await websocket.send_json(message)
            except Exception:  # noqa: BLE001 - a failed client must not stop the rest
                LOGGER.debug("Dropping metro WebSocket client after send failure")
                await self.disconnect(websocket)
