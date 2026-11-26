from datetime import datetime, timedelta, timezone

import pytest
from requests.exceptions import ConnectionError as RequestsConnectionError
from requests.exceptions import HTTPError
from src.exceptions.exceptions import MetroParseError, MetroScrapeError
from src.models.metro import EstadoServicioMetro
from src.services import metro_status
from src.services.metro_status import (
    NORMAL_TEXT,
    STATUS_URL,
    fetch_service_status_text,
    is_normal_status,
    next_status,
    parse_status_text,
)

NOW = datetime(2026, 11, 26, 8, 0, tzinfo=timezone.utc)
INCIDENT = "Servicio interrumpido entre Méndez Núñez y Alcázar Genil por incidencia técnica"


# --- parse_status_text -------------------------------------------------------


def test_parse_status_text_returns_plain_normal_text() -> None:
    assert parse_status_text("Servicio sin incidencias") == NORMAL_TEXT


def test_parse_status_text_collapses_whitespace() -> None:
    assert parse_status_text("\n  Servicio   interrumpido\r\n en Armilla  ") == "Servicio interrumpido en Armilla"


def test_parse_status_text_strips_inline_html_and_entities() -> None:
    raw = "<b>Servicio interrumpido</b> entre M&eacute;ndez N&uacute;&ntilde;ez<br/>y Alc&aacute;zar Genil"
    assert parse_status_text(raw) == "Servicio interrumpido entre Méndez Núñez y Alcázar Genil"


def test_parse_status_text_keeps_accents() -> None:
    assert parse_status_text(INCIDENT) == INCIDENT


@pytest.mark.parametrize(
    "raw",
    [
        '<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01//EN"><HTML><HEAD><TITLE>Length Required</TITLE>',
        "<html><body>Error</body></html>",
        "",
        "   \n ",
        "x" * 1001,
    ],
)
def test_parse_status_text_rejects_unexpected_payloads(raw: str) -> None:
    with pytest.raises(MetroParseError):
        parse_status_text(raw)


# --- is_normal_status --------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    ["Servicio sin incidencias", "SERVICIO SIN INCIDENCIAS", "servicio  sin incidencias.", "Servício sin incidéncias"],
)
def test_is_normal_status_accepts_variants(text: str) -> None:
    assert is_normal_status(text) is True


def test_is_normal_status_rejects_incidents() -> None:
    assert is_normal_status(INCIDENT) is False


# --- next_status -------------------------------------------------------------


def test_next_status_without_previous_starts_now() -> None:
    status = next_status(None, NORMAL_TEXT, NOW)

    assert status == EstadoServicioMetro(normal=True, texto=NORMAL_TEXT, desde=NOW, actualizado=NOW)


def test_next_status_same_text_keeps_since() -> None:
    previous = next_status(None, INCIDENT, NOW)
    later = NOW + timedelta(seconds=40)

    status = next_status(previous, INCIDENT, later)

    assert status.desde == NOW
    assert status.actualizado == later
    assert status.normal is False


def test_next_status_changed_text_resets_since() -> None:
    previous = next_status(None, INCIDENT, NOW)
    later = NOW + timedelta(minutes=30)

    status = next_status(previous, NORMAL_TEXT, later)

    assert status.desde == later
    assert status.normal is True


# --- fetch_service_status_text -----------------------------------------------


class FakeResponse:
    def __init__(self, body: bytes, status_code: int = 200, apparent_encoding: str = "utf-8") -> None:
        self.content = body
        self.status_code = status_code
        self.apparent_encoding = apparent_encoding
        self.encoding = "ISO-8859-1"  # what requests assumes for text/html without a charset

    @property
    def text(self) -> str:
        return self.content.decode(self.encoding)

    def raise_for_status(self) -> None:
        if self.status_code >= 400:  # noqa: PLR2004
            raise HTTPError(f"HTTP {self.status_code}")


class FakeSession:
    def __init__(self, response: FakeResponse | None = None, error: Exception | None = None) -> None:
        self.response = response
        self.error = error
        self.calls: list[tuple[str, dict]] = []

    def post(self, url: str, **kwargs) -> FakeResponse:
        self.calls.append((url, kwargs))
        if self.error is not None:
            raise self.error
        return self.response


def test_fetch_posts_empty_body_with_timeout() -> None:
    session = FakeSession(FakeResponse(b"Servicio sin incidencias"))

    assert fetch_service_status_text(session=session) == NORMAL_TEXT

    url, kwargs = session.calls[0]
    assert url == STATUS_URL
    assert kwargs["data"] == ""  # sends Content-Length: 0; the site answers 411 otherwise
    assert kwargs["timeout"] == metro_status.REQUEST_TIMEOUT_SECONDS


def test_fetch_decodes_accented_text_with_the_detected_encoding() -> None:
    session = FakeSession(FakeResponse(INCIDENT.encode("utf-8"), apparent_encoding="utf-8"))

    assert fetch_service_status_text(session=session) == INCIDENT


def test_fetch_http_error_raises_scrape_error() -> None:
    session = FakeSession(FakeResponse(b"", status_code=503))

    with pytest.raises(MetroScrapeError):
        fetch_service_status_text(session=session)


def test_fetch_network_error_raises_scrape_error() -> None:
    session = FakeSession(error=RequestsConnectionError("down"))

    with pytest.raises(MetroScrapeError):
        fetch_service_status_text(session=session)
