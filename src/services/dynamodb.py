import json
import logging
import time
from datetime import datetime, timezone
from typing import Any

import boto3
from botocore.exceptions import ClientError

from src.config import get_settings
from src.models.metro import LlegadasMetro

logger = logging.getLogger(__name__)

PARTITION_KEY = "METRO_ARRIVALS"

# In-memory cache for Lambda warm instances
_cache: dict[str, Any] = {
    "data": None,
    "timestamp": 0,
}


def _get_cache_ttl() -> int:
    """Get cache TTL in seconds from settings."""
    settings = get_settings()
    return getattr(settings, "memory_cache_ttl", 5)


_dynamodb_table = None


def _get_dynamodb_table():
    global _dynamodb_table
    if _dynamodb_table is not None:
        return _dynamodb_table

    settings = get_settings()
    kwargs = {}
    if settings.aws_region:
        kwargs["region_name"] = settings.aws_region
    if settings.dynamodb_endpoint_url:
        kwargs["endpoint_url"] = settings.dynamodb_endpoint_url

    dynamodb = boto3.resource("dynamodb", **kwargs)
    _dynamodb_table = dynamodb.Table(settings.dynamodb_table_name)
    return _dynamodb_table


def store_metro_arrivals(llegadas: list[LlegadasMetro]) -> bool:
    """Store metro arrivals data in DynamoDB."""
    table = _get_dynamodb_table()

    # Serialize the data
    data = [llegada.model_dump(mode="json") for llegada in llegadas]
    timestamp = datetime.now(timezone.utc).isoformat()

    try:
        table.put_item(
            Item={
                "pk": PARTITION_KEY,
                "data": json.dumps(data),
                "updated_at": timestamp,
            }
        )
        logger.info("Successfully stored metro arrivals at %s", timestamp)
        return True
    except ClientError as e:
        logger.error("Failed to store metro arrivals: %s", e)
        return False


def get_metro_arrivals() -> list[LlegadasMetro] | None:
    """
    Retrieve metro arrivals data with in-memory caching.

    Cache hierarchy:
    1. In-memory cache (sub-millisecond, survives within Lambda warm instance)
    2. DynamoDB (5-10ms fallback)

    This provides <0.1ms response times for most requests while Lambda is warm.
    """
    cache_ttl = _get_cache_ttl()

    # Check in-memory cache first
    if _cache["data"] is not None:
        cache_age = time.time() - _cache["timestamp"]
        if cache_age < cache_ttl:
            logger.debug("Cache hit (age: %.2fs)", cache_age)
            return _cache["data"]
        logger.debug("Cache expired (age: %.2fs, ttl: %ds)", cache_age, cache_ttl)

    # Fetch from DynamoDB
    table = _get_dynamodb_table()

    try:
        response = table.get_item(Key={"pk": PARTITION_KEY})

        if "Item" not in response:
            logger.warning("No metro arrivals data found in DynamoDB")
            return None

        item = response["Item"]
        data = json.loads(item["data"])
        updated_at = item.get("updated_at", "unknown")

        logger.debug("Retrieved metro arrivals from DynamoDB (updated: %s)", updated_at)

        llegadas = [LlegadasMetro.model_validate(llegada) for llegada in data]

        # Update in-memory cache
        _cache["data"] = llegadas
        _cache["timestamp"] = time.time()

        return llegadas

    except ClientError as e:
        logger.error("Failed to retrieve metro arrivals: %s", e)
        return None
    except (json.JSONDecodeError, KeyError) as e:
        logger.error("Failed to parse metro arrivals data: %s", e)
        return None


def clear_cache() -> None:
    """Clear the in-memory cache. Useful for testing."""
    _cache["data"] = None
    _cache["timestamp"] = 0
    logger.debug("In-memory cache cleared")


def get_metro_arrival_by_stop(id_parada: str) -> LlegadasMetro | None:
    """Retrieve metro arrivals for a specific stop from DynamoDB."""
    llegadas = get_metro_arrivals()

    if llegadas is None:
        return None

    for llegada in llegadas:
        if llegada.parada.id == id_parada:
            return llegada

    return None


def get_data_freshness() -> dict[str, Any] | None:
    """Get information about when the data was last updated."""
    table = _get_dynamodb_table()

    try:
        response = table.get_item(
            Key={"pk": PARTITION_KEY},
            ProjectionExpression="updated_at",
        )

        if "Item" not in response:
            return None

        return {"updated_at": response["Item"].get("updated_at")}

    except ClientError as e:
        logger.error("Failed to get data freshness: %s", e)
        return None
