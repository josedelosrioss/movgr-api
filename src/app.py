import asyncio
import os
from contextlib import asynccontextmanager, suppress

from fastapi import APIRouter, FastAPI, WebSocket, WebSocketDisconnect, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from src.exceptions.handler import add_exception_handler
from src.routers.bus import router as bus_api
from src.routers.metro import router as metro_api
from src.services import metro as metro_service
from src.services.metro_refresher import refresh_loop, snapshot_message, stale_message
from src.services.metro_status import InMemoryServiceStatusStore
from src.services.metro_status_refresher import status_refresh_loop
from src.services.metro_store import InMemoryMetroSnapshotStore
from src.services.ws_manager import WsManager

ws_manager = WsManager()


def _refresher_enabled() -> bool:
    return os.getenv("METRO_REFRESHER_ENABLED", "true").lower() == "true"


@asynccontextmanager
async def lifespan(app: FastAPI):
    tasks: list[asyncio.Task] = []
    if _refresher_enabled():
        store = InMemoryMetroSnapshotStore()
        metro_service.set_snapshot_store(store)
        tasks.append(asyncio.create_task(refresh_loop(store, ws_manager)))

        status_store = InMemoryServiceStatusStore()
        metro_service.set_status_store(status_store)
        tasks.append(asyncio.create_task(status_refresh_loop(status_store)))
    try:
        yield
    finally:
        for task in tasks:
            task.cancel()
        for task in tasks:
            with suppress(asyncio.CancelledError):
                await task


app = FastAPI(
    title="MovGR",
    description=("API para información de transportes urbanos de Granada"),
    version="0.1.1",
    contact={
        "name": "Miguel Ángel Fernández Gutiérrez",
        "url": "https://mianfg.me",
        "email": "hello@mianfg.me",
    },
    lifespan=lifespan,
)

if cors_origins := os.getenv("CORS_ORIGINS"):
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[origin.strip() for origin in cors_origins.split(",")],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


add_exception_handler(app)


@app.get("/")
async def health_check() -> Response:
    return Response(status_code=status.HTTP_200_OK)


@app.websocket("/ws/metro")
async def metro_ws(websocket: WebSocket) -> None:
    await ws_manager.accept(websocket)
    snapshot = metro_service.get_current_snapshot_or_none()
    if snapshot is not None:
        await websocket.send_json(snapshot_message(snapshot))
        if metro_service.is_stale(snapshot):
            await websocket.send_json(stale_message(snapshot))
    # Register only after the on-connect send so broadcast() never sends concurrently
    # with the line above on the same (not concurrency-safe) socket.
    await ws_manager.register(websocket)
    try:
        while True:
            # We ignore client messages; receiving is only how we detect a disconnect.
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await ws_manager.disconnect(websocket)


router = APIRouter()

router.include_router(bus_api, prefix="/bus", tags=["bus"])
router.include_router(metro_api, prefix="/metro", tags=["metro"])

app.include_router(router)

try:
    from mangum import Mangum

    handler = Mangum(
        app,
        api_gateway_base_path=None,
        lifespan="off",
    )
except ImportError:
    handler = None


def run() -> None:
    import uvicorn

    uvicorn.run("src.app:app", host="localhost", port=8080, reload=True, workers=1)


if __name__ == "__main__":
    run()
