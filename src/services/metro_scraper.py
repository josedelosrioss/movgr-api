import logging
import re
import time
import unicodedata
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup
from requests import Session
from requests.exceptions import RequestException

from src.exceptions.exceptions import MetroParseError, MetroScrapeError
from src.models.metro import DireccionMetro, LlegadasMetro, ParadaMetro, ProximoMetro
from src.services.metro_catalog import paradas
from src.services.metro_store import MetroSnapshot

LOGGER = logging.getLogger(__name__)

HEADERS = {
    "accept": "*/*",
    "content-type": "application/x-www-form-urlencoded",
    "dnt": "1",
    "origin": "https://metropolitanogranada.es",
    "priority": "u=0, i",
    "referer": "https://metropolitanogranada.es/horariosreal",
}
URL = "https://metropolitanogranada.es/MGhorariosreal.asp"
REQUEST_TIMEOUT_SECONDS = 10
SESSION = requests.Session()
NAME_ALIASES: dict[str, str] = {}


def _normalize_stop_name(name: str) -> str:
    normalized = unicodedata.normalize("NFKD", name)
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    normalized = re.sub(r"[^A-Za-z0-9]+", " ", normalized).strip().upper()
    return re.sub(r"\s+", " ", normalized)


def _extract_minutes(value: str) -> int | None:
    digits = "".join(re.findall(r"\d+", value))
    if not digits:
        return None
    return int(digits)


def _catalog_by_name(catalog: list[ParadaMetro]) -> dict[str, ParadaMetro]:
    return {_normalize_stop_name(parada.nombre): parada for parada in catalog}


def parse_llegadas_html(
    html: str,
    catalog: list[ParadaMetro] | None = None,
) -> list[LlegadasMetro]:
    catalog = catalog or paradas
    catalog_names = _catalog_by_name(catalog)

    soup = BeautifulSoup(html, "html.parser")
    datos = [cell.getText().strip() for cell in soup.find_all("td")]
    if not datos or len(datos) % 5 != 0:  # noqa: PLR2004
        raise MetroParseError("La respuesta del metro no tiene el formato esperado")

    paradas_soup = [datos[i : i + 5] for i in range(0, len(datos), 5)]

    llegadas_por_parada: dict[str, LlegadasMetro] = {}
    for parada_soup in paradas_soup:
        raw_name = parada_soup[0]
        normalized_name = _normalize_stop_name(raw_name)
        canonical_name = NAME_ALIASES.get(normalized_name, normalized_name)
        parada = catalog_names.get(canonical_name)
        if parada is None:
            raise MetroParseError(f"Parada desconocida en scrape: {raw_name}")

        proximos = []
        for index, value in enumerate(parada_soup[1:]):
            minutes = _extract_minutes(value)
            if minutes is None:
                continue
            proximos.append(
                ProximoMetro(
                    direccion=DireccionMetro.Armilla if index >= 2 else DireccionMetro.Albolote,  # noqa: PLR2004
                    minutos=minutes,
                ),
            )

        llegadas_por_parada[parada.id] = LlegadasMetro(
            parada=parada,
            proximos=sorted(proximos, key=lambda proximo: proximo.minutos),
        )

    missing_ids = [parada.id for parada in catalog if parada.id not in llegadas_por_parada]
    if missing_ids:
        raise MetroParseError("Faltan paradas en el scrape de metro")

    return [llegadas_por_parada[parada.id] for parada in catalog]


def fetch_llegadas_snapshot(
    session: Session | None = None,
    catalog: list[ParadaMetro] | None = None,
) -> MetroSnapshot:
    current_session = session or SESSION
    start = time.perf_counter()
    try:
        response = current_session.post(
            URL,
            headers=HEADERS,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
    except RequestException as exc:
        raise MetroScrapeError("No se pudo obtener la información del metro") from exc

    response.encoding = response.apparent_encoding
    arrivals = parse_llegadas_html(response.text, catalog=catalog)
    latency_ms = int((time.perf_counter() - start) * 1000)
    LOGGER.info("Fetched metro snapshot in %sms", latency_ms)

    return MetroSnapshot(
        fetched_at=datetime.now(timezone.utc),
        arrivals=arrivals,
        source_latency_ms=latency_ms,
    )
