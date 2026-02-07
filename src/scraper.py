"""
Metro Scraper Lambda Handler

This module scrapes metro arrival data from metropolitanogranada.es
and stores it in DynamoDB. It's designed to run as a scheduled Lambda
function triggered by EventBridge every 30-60 seconds.
"""

import csv
import logging
import os
import re
import urllib3
from typing import Any

import requests
from bs4 import BeautifulSoup

# Suppress SSL warnings for metropolitanogranada.es (certificate chain issues)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from src.config import get_settings
from src.models.metro import LlegadasMetro, ParadaMetro, ProximoMetro
from src.services.dynamodb import store_metro_arrivals

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Add console handler if not already present (for Lambda)
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
    logger.addHandler(handler)


def _load_paradas() -> list[ParadaMetro]:
    """Load metro stops from CSV file."""
    csv_path = os.path.join(os.path.dirname(__file__), "data/metro/paradas.csv")
    with open(csv_path, "r") as file:
        reader = csv.reader(file)
        next(reader)  # Skip header
        return [ParadaMetro(linea=row[0], id=row[1], nombre=row[2]) for row in reader]


def scrape_metro_arrivals() -> list[LlegadasMetro]:
    """
    Scrape metro arrival data from metropolitanogranada.es.

    Returns:
        List of LlegadasMetro objects with current arrival times.

    Raises:
        requests.RequestException: If the HTTP request fails.
        ValueError: If the response data cannot be parsed.
    """
    settings = get_settings()
    paradas = _load_paradas()

    headers = {
        "accept": "*/*",
        "content-type": "application/x-www-form-urlencoded",
        "dnt": "1",
        "origin": "https://metropolitanogranada.es",
        "priority": "u=0, i",
        "referer": "https://metropolitanogranada.es/horariosreal",
    }

    logger.info("Scraping metro data from %s", settings.metro_source_url)

    response = requests.post(
        settings.metro_source_url,
        headers=headers,
        timeout=settings.scrape_timeout,
        verify=False,  # metropolitanogranada.es has SSL issues with Lambda's CA bundle
    )
    response.raise_for_status()
    response.encoding = response.apparent_encoding

    soup = BeautifulSoup(response.text, "html.parser")
    datos = [cell.getText().strip() for cell in soup.find_all("td")]

    if not datos:
        raise ValueError("No data found in metro response")

    # Parse data: each stop has 5 columns (name + 4 arrival times)
    columns_per_stop = 5
    paradas_soup = [datos[i : i + columns_per_stop] for i in range(0, len(datos), columns_per_stop)]

    # Extract numeric values from arrival columns
    for parada in paradas_soup:
        parada[1:] = ["".join(re.findall(r"\d+", col)) for col in parada[1:]]

    llegadas = []
    for parada_soup, parada in zip(paradas_soup, paradas):
        proximos = []
        for i, col in enumerate(parada_soup[1:]):
            if col:
                # First 2 columns are Albolote direction, last 2 are Armilla
                direccion = "Armilla" if i >= 2 else "Albolote"  # noqa: PLR2004
                proximos.append(ProximoMetro(direccion=direccion, minutos=int(col)))

        proximos.sort(key=lambda p: p.minutos)
        llegadas.append(LlegadasMetro(parada=parada, proximos=proximos))

    logger.info("Successfully scraped %d metro stops", len(llegadas))
    return llegadas


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """
    AWS Lambda handler for scheduled metro data scraping.

    This function is triggered by EventBridge on a schedule (e.g., every 30 seconds)
    to fetch fresh metro arrival data and store it in DynamoDB.

    Args:
        event: Lambda event (from EventBridge, typically empty for scheduled events)
        context: Lambda context object

    Returns:
        Dict with status code and message
    """
    logger.info("Starting scheduled metro scrape")

    try:
        # Scrape fresh data
        llegadas = scrape_metro_arrivals()

        # Store in DynamoDB
        success = store_metro_arrivals(llegadas)

        if success:
            return {
                "statusCode": 200,
                "body": f"Successfully scraped and stored {len(llegadas)} metro stops",
            }
        else:
            return {
                "statusCode": 500,
                "body": "Failed to store metro data in DynamoDB",
            }

    except requests.RequestException as e:
        logger.error("Failed to scrape metro data: %s", e)
        return {
            "statusCode": 502,
            "body": f"Failed to fetch metro data: {str(e)}",
        }
    except ValueError as e:
        logger.error("Failed to parse metro data: %s", e)
        return {
            "statusCode": 500,
            "body": f"Failed to parse metro data: {str(e)}",
        }
    except Exception as e:
        logger.exception("Unexpected error in metro scraper")
        return {
            "statusCode": 500,
            "body": f"Unexpected error: {str(e)}",
        }


# Allow running locally for testing
if __name__ == "__main__":
    result = handler({}, None)
    print(result)
