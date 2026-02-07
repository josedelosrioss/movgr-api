from fastapi import APIRouter, FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from src.config import get_settings
from src.exceptions.handler import add_exception_handler
from src.routers.bus import router as bus_api
from src.routers.metro import router as metro_api

settings = get_settings()

app = FastAPI(
    title="MovGR",
    description=("API para información de transportes urbanos de Granada"),
    version="0.2.0",
    contact={
        "name": "Miguel Ángel Fernández Gutiérrez",
        "url": "https://mianfg.me",
        "email": "hello@mianfg.me",
    },
)

if settings.cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[origin.strip() for origin in settings.cors_origins.split(",")],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


add_exception_handler(app)


@app.get("/")
async def health_check() -> Response:
    return Response(status_code=status.HTTP_200_OK)


@app.get("/health")
async def health() -> dict:
    """Health check endpoint with data freshness info."""
    health_info = {
        "status": "healthy",
        "use_dynamodb": settings.use_dynamodb,
    }

    if settings.use_dynamodb:
        from src.services.dynamodb import get_data_freshness

        freshness = get_data_freshness()
        if freshness:
            health_info["data_updated_at"] = freshness.get("updated_at")
        else:
            health_info["data_status"] = "no_data"

    return health_info


router = APIRouter()

router.include_router(bus_api, prefix="/bus", tags=["bus"])
router.include_router(metro_api, prefix="/metro", tags=["metro"])

app.include_router(router)

try:
    from mangum import Mangum

    # Configure Mangum with the API stage path for proper routing
    _api_base_path = f"/{settings.api_stage}" if settings.api_stage else None
    handler = Mangum(
        app,
        api_gateway_base_path=_api_base_path,
        lifespan="off",
    )
except ImportError:
    handler = None


def run() -> None:
    import uvicorn

    uvicorn.run("src.app:app", host="localhost", port=8080, reload=True, workers=3)


if __name__ == "__main__":
    run()
