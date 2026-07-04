from fastapi import APIRouter, Response

from src.models.metro import LlegadasMetro, ParadaMetro
from src.services.metro import (
    get_llegadas_parada,
    get_llegadas_snapshot,
    get_snapshot_headers,
)
from src.services.metro_catalog import paradas as paradas_metro

router = APIRouter()


@router.get(
    "/paradas",
    response_model=list[ParadaMetro],
    response_description="Lista de paradas de metro",
)
def paradas() -> list[ParadaMetro]:
    return paradas_metro


@router.get(
    "/llegadas",
    response_model=list[LlegadasMetro],
    response_description="Obtener estado actual de todas las paradas de metro",
)
def llegadas(response: Response) -> list[LlegadasMetro]:
    snapshot = get_llegadas_snapshot()
    response.headers.update(get_snapshot_headers(snapshot))
    return snapshot.arrivals


@router.get(
    "/llegadas/{id_parada}",
    response_model=LlegadasMetro,
    response_description="Información de parada de metro",
)
def llegadas_parada(id_parada: str, response: Response) -> LlegadasMetro:
    snapshot = get_llegadas_snapshot()
    response.headers.update(get_snapshot_headers(snapshot))
    return get_llegadas_parada(id_parada, snapshot=snapshot)
