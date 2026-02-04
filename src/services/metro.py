import csv
import logging
import os
import re

import requests
from bs4 import BeautifulSoup

from src.config import get_settings
from src.exceptions.exceptions import ParadaNotFoundError
from src.models.metro import (
    LlegadasMetro,
    ParadaMetro,
    ProximoMetro,
)

logger = logging.getLogger(__name__)


def get_paradas() -> list[ParadaMetro]:
    with open(os.path.join(os.path.dirname(__file__), "../data/metro/paradas.csv"), "r") as file:
        reader = csv.reader(file)
        next(reader)
        paradas = [ParadaMetro(linea=row[0], id=row[1], nombre=row[2]) for row in reader]
    return paradas


paradas = get_paradas()


def _scrape_llegadas() -> list[LlegadasMetro]:
    """Legacy: Scrape metro arrivals directly from source (used when DynamoDB is disabled)."""
    settings = get_settings()

    headers = {
        "accept": "*/*",
        "content-type": "application/x-www-form-urlencoded",
        "dnt": "1",
        "origin": "https://metropolitanogranada.es",
        "priority": "u=0, i",
        "referer": "https://metropolitanogranada.es/horariosreal",
    }

    response = requests.post(
        settings.metro_source_url,
        headers=headers,
        timeout=settings.scrape_timeout,
    )
    response.encoding = response.apparent_encoding

    soup = BeautifulSoup(response.text, "html.parser")

    datos = [cell.getText().strip() for cell in soup.find_all("td")]
    columns_per_stop = 5
    paradas_soup = [datos[i : i + columns_per_stop] for i in range(0, len(datos), columns_per_stop)]

    for parada in paradas_soup:
        parada[1:] = ["".join(re.findall(r"\d+", col)) for col in parada[1:]]

    return [
        LlegadasMetro(
            parada=parada,
            proximos=sorted(
                [
                    ProximoMetro(
                        direccion="Armilla" if i >= 2 else "Albolote",  # noqa: PLR2004
                        minutos=int(col),
                    )
                    for i, col in enumerate(parada_soup[1:])
                    if col
                ],
                key=lambda proximo: proximo.minutos,
            ),
        )
        for parada_soup, parada in zip(paradas_soup, paradas)
    ]


def get_llegadas() -> list[LlegadasMetro]:
    """
    Get metro arrivals data.

    If USE_DYNAMODB is enabled (default), reads from DynamoDB cache.
    Otherwise, falls back to direct scraping (legacy mode).
    """
    settings = get_settings()

    if settings.use_dynamodb:
        from src.services.dynamodb import get_metro_arrivals

        llegadas = get_metro_arrivals()
        if llegadas is not None:
            return llegadas

        logger.warning("DynamoDB returned no data, falling back to direct scraping")

    return _scrape_llegadas()


def get_llegadas_parada(id_parada: str) -> LlegadasMetro:
    """
    Get metro arrivals for a specific stop.

    Args:
        id_parada: The stop ID to look up.

    Returns:
        LlegadasMetro object for the specified stop.

    Raises:
        ParadaNotFoundError: If the stop ID is not found.
    """
    settings = get_settings()

    if settings.use_dynamodb:
        from src.services.dynamodb import get_metro_arrival_by_stop

        llegada = get_metro_arrival_by_stop(id_parada)
        if llegada is not None:
            return llegada

        # Check if stop exists but has no data vs stop doesn't exist
        for parada in paradas:
            if parada.id == id_parada:
                logger.warning("Stop %s exists but no arrival data in DynamoDB", id_parada)
                break
        else:
            raise ParadaNotFoundError from None

        logger.warning("Falling back to direct scraping for stop %s", id_parada)

    # Fallback to direct scraping
    proximos = _scrape_llegadas()
    for proximo in proximos:
        if proximo.parada.id == id_parada:
            return proximo
    raise ParadaNotFoundError from None
