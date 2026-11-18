from fastapi import FastAPI, HTTPException, Request

from src.exceptions.exceptions import (
    LineaNotFoundError,
    MetroDataUnavailableError,
    ParadaNotFoundError,
    ParadaRequestError,
)


async def __exception_handler(request: Request, exc: Exception) -> None:  # noqa: ARG001
    if isinstance(exc, ParadaNotFoundError):
        raise HTTPException(
            status_code=404,
            detail="Parada no encontrada",
        )
    if isinstance(exc, LineaNotFoundError):
        raise HTTPException(
            status_code=404,
            detail="Línea no encontrada",
        )
    if isinstance(exc, ParadaRequestError):
        raise HTTPException(
            status_code=500,
            detail="Hubo un error con la petición",
        )
    if isinstance(exc, MetroDataUnavailableError):
        raise HTTPException(
            status_code=503,
            detail="No hay datos recientes de metro disponibles",
        )

    raise exc


def add_exception_handler(app: FastAPI) -> None:
    app.add_exception_handler(ParadaNotFoundError, __exception_handler)
    app.add_exception_handler(ParadaRequestError, __exception_handler)
    app.add_exception_handler(LineaNotFoundError, __exception_handler)
    app.add_exception_handler(MetroDataUnavailableError, __exception_handler)
