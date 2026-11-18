import asyncio

from src.services.ws_manager import WsManager


class FakeWebSocket:
    def __init__(self, *, fail_on_send: bool = False) -> None:
        self.accepted = False
        self.sent: list[dict] = []
        self._fail_on_send = fail_on_send

    async def accept(self) -> None:
        self.accepted = True

    async def send_json(self, message: dict) -> None:
        if self._fail_on_send:
            raise RuntimeError("client gone")
        self.sent.append(message)


def test_connect_accepts_and_tracks_client() -> None:
    manager = WsManager()
    ws = FakeWebSocket()

    asyncio.run(manager.connect(ws))

    assert ws.accepted is True
    assert manager.client_count == 1


def test_broadcast_delivers_to_all_clients() -> None:
    manager = WsManager()
    first, second = FakeWebSocket(), FakeWebSocket()

    async def scenario() -> None:
        await manager.connect(first)
        await manager.connect(second)
        await manager.broadcast({"type": "snapshot"})

    asyncio.run(scenario())

    assert first.sent == [{"type": "snapshot"}]
    assert second.sent == [{"type": "snapshot"}]


def test_broadcast_drops_failed_client_without_affecting_others() -> None:
    manager = WsManager()
    healthy = FakeWebSocket()
    broken = FakeWebSocket(fail_on_send=True)

    async def scenario() -> None:
        await manager.connect(healthy)
        await manager.connect(broken)
        await manager.broadcast({"type": "snapshot"})

    asyncio.run(scenario())

    assert healthy.sent == [{"type": "snapshot"}]
    assert manager.client_count == 1


def test_disconnect_removes_client() -> None:
    manager = WsManager()
    ws = FakeWebSocket()

    async def scenario() -> None:
        await manager.connect(ws)
        await manager.disconnect(ws)

    asyncio.run(scenario())

    assert manager.client_count == 0
