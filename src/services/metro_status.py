"""Estado del servicio de metro publicado por metropolitanogranada.es.

La portada de la web consulta ``POST /servicioEstado`` cada 10 s y muestra el texto
devuelto: "Servicio sin incidencias" cuando todo va bien, o el texto de la incidencia.
"""

import logging
import re
import unicodedata
from datetime import datetime

from bs4 import BeautifulSoup
from requests import Session
from requests.exceptions import RequestException

from src.exceptions.exceptions import MetroParseError, MetroScrapeError
from src.models.metro import EstadoServicioMetro
from src.services.metro_scraper import HEADERS, REQUEST_TIMEOUT_SECONDS, SESSION

LOGGER = logging.getLogger(__name__)

STATUS_URL = "https://metropolitanogranada.es/servicioEstado"
NORMAL_TEXT = "Servicio sin incidencias"
MAX_STATUS_LENGTH = 1000
_HTML_DOCUMENT = re.compile(r"^\s*(<!doctype|<html)", re.IGNORECASE)


def _comparable(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    normalized = re.sub(r"[^A-Za-z0-9]+", " ", normalized).strip().casefold()
    return re.sub(r"\s+", " ", normalized)


def parse_status_text(raw: str) -> str:
    """Return the status as clean plain text, rejecting anything that is not a status message."""
    if _HTML_DOCUMENT.match(raw or ""):
        raise MetroParseError("La respuesta de estado del metro es una página HTML, no un estado")

    # The site inserts the text as innerHTML, so it may contain inline tags or entities.
    text = BeautifulSoup(raw or "", "html.parser").get_text(" ")
    text = re.sub(r"\s+", " ", text).strip()

    if not text:
        raise MetroParseError("La respuesta de estado del metro está vacía")
    if len(text) > MAX_STATUS_LENGTH:
        raise MetroParseError("La respuesta de estado del metro es demasiado larga")
    return text


def is_normal_status(text: str) -> bool:
    return _comparable(text) == _comparable(NORMAL_TEXT)


def next_status(previous: EstadoServicioMetro | None, text: str, now: datetime) -> EstadoServicioMetro:
    """Build the new status, keeping ``desde`` while the text stays exactly the same."""
    unchanged = previous is not None and previous.texto == text
    return EstadoServicioMetro(
        normal=is_normal_status(text),
        texto=text,
        desde=previous.desde if unchanged else now,
        actualizado=now,
    )


def fetch_service_status_text(session: Session | None = None) -> str:
    current_session = session or SESSION
    try:
        # data="" sends Content-Length: 0; without it the site answers HTTP 411.
        response = current_session.post(STATUS_URL, headers=HEADERS, data="", timeout=REQUEST_TIMEOUT_SECONDS)
        response.raise_for_status()
    except RequestException as exc:
        raise MetroScrapeError("No se pudo obtener el estado del servicio de metro") from exc

    # The response has no charset; requests would assume ISO-8859-1 and garble accents.
    response.encoding = response.apparent_encoding
    return parse_status_text(response.text)


class InMemoryServiceStatusStore:
    def __init__(self, status: EstadoServicioMetro | None = None) -> None:
        self._status = status

    def get_current(self) -> EstadoServicioMetro | None:
        return self._status

    def put_current(self, status: EstadoServicioMetro) -> None:
        self._status = status
