import csv
import os

from src.models.metro import ParadaMetro


def get_paradas() -> list[ParadaMetro]:
    with open(os.path.join(os.path.dirname(__file__), "../data/metro/paradas.csv"), "r") as file:
        reader = csv.reader(file)
        next(reader)
        paradas = [ParadaMetro(linea=row[0], id=row[1], nombre=row[2]) for row in reader]
    return paradas


paradas = get_paradas()
