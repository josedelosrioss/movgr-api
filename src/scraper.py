from src.services.metro_scraper import fetch_llegadas_snapshot
from src.services.metro_store import build_snapshot_store


def handler(event: dict | None, context: object) -> dict:  # noqa: ARG001
    snapshot_store = build_snapshot_store(require_dynamodb=True)
    snapshot = fetch_llegadas_snapshot()
    snapshot_store.put_current(snapshot)

    return {
        "stored_at": snapshot.fetched_at.isoformat(),
        "paradas": len(snapshot.arrivals),
        "source_latency_ms": snapshot.source_latency_ms,
        "event": event or {},
    }
