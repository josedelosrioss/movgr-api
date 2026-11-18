class BusGranadaAPIError(Exception):
    pass


class ParadaNotFoundError(BusGranadaAPIError):
    pass


class LineaNotFoundError(BusGranadaAPIError):
    pass


class ParadaRequestError(BusGranadaAPIError):
    pass


class MetroDataUnavailableError(BusGranadaAPIError):
    pass


class MetroParseError(BusGranadaAPIError):
    pass


class MetroScrapeError(BusGranadaAPIError):
    pass


class MetroSnapshotStoreError(BusGranadaAPIError):
    pass
