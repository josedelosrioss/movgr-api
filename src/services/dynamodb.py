import json
import logging
from datetime import datetime, timezone
from typing import Any

import boto3
from botocore.exceptions import ClientError

from src.config import get_settings
from src.models.metro import LlegadasMetro

logger = logging.getLogger(__name__)

PARTITION_KEY = "METRO_ARRIVALS"


def _get_dynamodb_table():
    settings = get_settings()
    dynamodb = boto3.resource(
        "dynamodb",
        region_name=settings.aws_region,
        endpoint_url=settings.dynamodb_endpoint_url,
    )
    return dynamodb.Table(settings.dynamodb_table_name)


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
    """Retrieve metro arrivals data from DynamoDB."""
    table = _get_dynamodb_table()

    try:
        response = table.get_item(Key={"pk": PARTITION_KEY})

        if "Item" not in response:
            logger.warning("No metro arrivals data found in DynamoDB")
            return None

        item = response["Item"]
        data = json.loads(item["data"])
        updated_at = item.get("updated_at", "unknown")

        logger.debug("Retrieved metro arrivals from %s", updated_at)

        return [LlegadasMetro.model_validate(llegada) for llegada in data]

    except ClientError as e:
        logger.error("Failed to retrieve metro arrivals: %s", e)
        return None
    except (json.JSONDecodeError, KeyError) as e:
        logger.error("Failed to parse metro arrivals data: %s", e)
        return None


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
