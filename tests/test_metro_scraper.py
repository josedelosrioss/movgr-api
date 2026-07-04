from pathlib import Path

import pytest

from src.exceptions.exceptions import MetroParseError
from src.models.metro import DireccionMetro, ParadaMetro
from src.services.metro_scraper import parse_llegadas_html

FIXTURES_DIR = Path(__file__).parent / "fixtures"

CATALOG = [
    ParadaMetro(linea="1", id="101", nombre="Albolote"),
    ParadaMetro(linea="1", id="105", nombre="Maracena"),
]


def _read_fixture(name: str) -> str:
    return (FIXTURES_DIR / name).read_text(encoding="utf-8")


def test_parse_llegadas_html_orders_results_by_catalog() -> None:
    arrivals = parse_llegadas_html(_read_fixture("metro_small_reordered.html"), catalog=CATALOG)

    assert [arrival.parada.id for arrival in arrivals] == ["101", "105"]
    assert arrivals[0].proximos[0].direccion == DireccionMetro.Albolote
    assert arrivals[1].proximos[0].direccion == DireccionMetro.Armilla


def test_parse_llegadas_html_rejects_unknown_stop() -> None:
    with pytest.raises(MetroParseError):
        parse_llegadas_html(_read_fixture("metro_small_unknown.html"), catalog=CATALOG)


def test_parse_llegadas_html_rejects_malformed_payload() -> None:
    with pytest.raises(MetroParseError):
        parse_llegadas_html(_read_fixture("metro_small_malformed.html"), catalog=CATALOG)
