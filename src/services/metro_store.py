import os
from collections.abc import Callable
from datetime import datetime
from typing import Protocol

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from src.exceptions.exceptions import MetroSnapshotStoreError
from src.models.metro import LlegadasMetro
from src.models.base import MovGrBaseModel

METRO_CURRENT_PK = "metro_current"


class MetroSnapshot(MovGrBaseModel):
    fetched_at: datetime
    arrivals: list[LlegadasMetro]
    source_latency_ms: int | None = None


class MetroSnapshotStore(Protocol):
    def get_current(self) -> MetroSnapshot | None:
        ...

    def put_current(self, snapshot: MetroSnapshot) -> None:
        ...


class InMemoryMetroSnapshotStore:
    def __init__(self, snapshot: MetroSnapshot | None = None) -> None:
        self._snapshot = snapshot

    def get_current(self) -> MetroSnapshot | None:
        return self._snapshot

    def put_current(self, snapshot: MetroSnapshot) -> None:
        self._snapshot = snapshot


class DynamoMetroSnapshotStore:
    def __init__(
        self,
        table_name: str,
        dynamodb_resource_factory: Callable[[], object] | None = None,
    ) -> None:
        self.table_name = table_name
        resource_factory = dynamodb_resource_factory or (lambda: boto3.resource("dynamodb"))
        self._table = resource_factory().Table(table_name)

    def get_current(self) -> MetroSnapshot | None:
        try:
            response = self._table.get_item(Key={"pk": METRO_CURRENT_PK})
        except (BotoCoreError, ClientError) as exc:
            raise MetroSnapshotStoreError("No se pudo recuperar el estado de metro") from exc

        item = response.get("Item")
        if item is None:
            return None

        return MetroSnapshot(
            fetched_at=item["fetched_at"],
            arrivals=item["arrivals"],
            source_latency_ms=item.get("source_latency_ms"),
        )

    def put_current(self, snapshot: MetroSnapshot) -> None:
        item = {
            "pk": METRO_CURRENT_PK,
            "fetched_at": snapshot.fetched_at.isoformat(),
            "arrivals": [arrival.model_dump(mode="json") for arrival in snapshot.arrivals],
        }
        if snapshot.source_latency_ms is not None:
            item["source_latency_ms"] = snapshot.source_latency_ms

        try:
            self._table.put_item(Item=item)
        except (BotoCoreError, ClientError) as exc:
            raise MetroSnapshotStoreError("No se pudo guardar el estado de metro") from exc


def build_snapshot_store(*, require_dynamodb: bool = False) -> MetroSnapshotStore | None:
    use_dynamodb = os.getenv("USE_DYNAMODB", "false").lower() == "true"
    table_name = os.getenv("DYNAMODB_TABLE_NAME")

    if not use_dynamodb:
        if require_dynamodb:
            raise MetroSnapshotStoreError("USE_DYNAMODB debe estar habilitado para el scraper")
        return None

    if not table_name:
        raise MetroSnapshotStoreError("DYNAMODB_TABLE_NAME es obligatorio cuando USE_DYNAMODB=true")

    return DynamoMetroSnapshotStore(table_name=table_name)
