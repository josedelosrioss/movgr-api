import csv
import os

import requests
from bs4 import BeautifulSoup

from src.exceptions.exceptions import (
    LineaNotFoundError,
    ParadaNotFoundError,
    ParadaRequestError,
)
from src.models.bus import LineaBus, LlegadasBus, ParadaBus, ProximoBus


def get_paradas() -> dict[int, ParadaBus]:
    with open(os.path.join(os.path.dirname(__file__), "../data/bus/paradas.csv"), "r") as file:
        reader = csv.reader(file)
        next(reader)
        paradas = {int(row[0]): ParadaBus(id=row[0], nombre=row[1]) for row in reader}
    return paradas


def get_lineas() -> dict[str, LineaBus]:
    with open(os.path.join(os.path.dirname(__file__), "../data/bus/lineas.csv"), "r") as file:
        reader = csv.reader(file)
        next(reader)
        lineas = {row[0]: LineaBus(id=row[0], nombre=row[1]) for row in reader}
    return lineas


paradas = get_paradas()
lineas = get_lineas()


def __extract_parada_from_soup(soup: BeautifulSoup, id_parada: int) -> ParadaBus:
    """Extract parada information from BeautifulSoup object."""
    # Check for error message
    message = soup.find("div", {"class": "message"})
    if message and "no existe" in message.getText():
        raise ParadaNotFoundError from None

    # Extract the full parada name from mainhead
    mainhead = soup.find("div", {"class": "mainhead"})
    if mainhead:
        nombre_div = mainhead.find("div", {"style": lambda x: x and "color:" in x})
        if nombre_div:
            nombre_parada = nombre_div.getText().strip()
            nombre_parada = " ".join(nombre_parada.split())  # Clean whitespace
            return ParadaBus(id=id_parada, nombre=nombre_parada)

    # If we can't find the name, raise error
    raise ParadaNotFoundError from None


def get_parada(id_parada: int) -> ParadaBus:
    """Return parada information from the static bus catalog."""
    try:
        return paradas[id_parada]
    except KeyError:
        raise ParadaNotFoundError from None


def get_linea(id_linea: str) -> LineaBus:
    try:
        return lineas[id_linea]
    except KeyError:
        raise LineaNotFoundError from None


def __perform_request(num_parada: int) -> dict:
    headers = {
        "accept": (
            "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,"
            "image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7"
        ),
        "accept-language": "en-US,en;q=0.9",
        "cache-control": "max-age=0",
        "dnt": "1",
        "origin": "https://www.transportesrober.com",
        "referer": "https://www.transportesrober.com/flotamovimiento/paradas.htm",
        "sec-fetch-dest": "document",
        "sec-fetch-mode": "navigate",
        "sec-fetch-site": "same-origin",
        "upgrade-insecure-requests": "1",
        "user-agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36"
        ),
    }

    files = {
        "excel": (None, ""),
        "parada": (None, str(num_parada)),
    }

    response = requests.post(
        "https://www.transportesrober.com/flotamovimiento/paradas.htm",
        headers=headers,
        files=files,
        timeout=5,
    )

    if response.status_code != 200:  # noqa: PLR2004
        raise ParadaRequestError

    # Ensure proper UTF-8 encoding
    response.encoding = "utf-8"
    return response


def get_llegadas_parada(num_parada: int) -> LlegadasBus:
    # Perform single request to get both parada info and bus arrivals
    req = __perform_request(num_parada)
    soup = BeautifulSoup(req.text, "html.parser")

    # Extract parada information
    parada = __extract_parada_from_soup(soup, num_parada)

    # Check if there's a message indicating no arrivals
    message = soup.find("div", {"class": "message"})
    if message:
        return LlegadasBus(parada=parada, proximos=[])

    proximos: list[ProximoBus] = []
    table = soup.find("div", {"class": "tf"})
    if table:
        rows = table.find_all("div", {"class": "tfr"})
        for row in rows:
            cols = row.find_all("div", {"class": "tfcc"})
            cols_s = row.find_all("div", {"class": "tfccs"})
            if len(cols) >= 3 and len(cols_s) >= 1:  # noqa: PLR2004
                # Find line number - it's inside a div with class "form_white" in the first column
                form_white_div = cols[0].find("div", {"class": "form_white"})
                if form_white_div:
                    id_linea = form_white_div.getText().strip()
                    try:
                        linea = get_linea(id_linea)
                    except LineaNotFoundError:
                        linea = LineaBus(id=id_linea)
                    # Destination is in the tfccs div
                    destino = cols_s[0].getText().strip()
                    # Minutes is in the third column (index 1, skipping the first which has the form)
                    minutos_text = cols[1].getText().strip()
                    minutos = int(minutos_text) if minutos_text.isdigit() else 0
                    proximos.append(
                        ProximoBus(
                            linea=linea,
                            destino=destino,
                            minutos=minutos,
                        ),
                    )

    return LlegadasBus(parada=parada, proximos=proximos)
