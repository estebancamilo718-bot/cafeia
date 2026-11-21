"""Consultas a Open-Meteo para el servidor MCP de clima.

Open-Meteo es gratuito y no requiere clave. Solo se envía el nombre de la
ciudad elegida (geocodificación) y sus coordenadas (pronóstico); nunca la
fotografía. Los datos se devuelven tal cual: este módulo no calcula riesgos.
"""

from __future__ import annotations

import logging

import httpx2 as httpx
from pydantic import BaseModel, ValidationError

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
FUENTE = "Open-Meteo (open-meteo.com), datos con licencia CC BY 4.0"
PAIS = "CO"
CIUDAD_PREDETERMINADA = "Ibagué"
TIEMPO_ESPERA_SEGUNDOS = 6.0
INTENTOS_CONEXION = 2
MAX_DIAS_PRONOSTICO = 7
MAX_LARGO_CIUDAD = 80


class ClimaNoDisponible(Exception):
    """Error mostrable al usuario cuando no se pudo obtener el clima."""


class Ubicacion(BaseModel):
    nombre: str
    departamento: str | None = None
    pais: str
    latitud: float
    longitud: float
    elevacion_m: float | None = None


class ClimaActual(BaseModel):
    ubicacion: Ubicacion
    hora_local: str
    temperatura_c: float
    humedad_relativa_pct: float
    precipitacion_mm: float
    fuente: str


class DiaPronostico(BaseModel):
    fecha: str
    temperatura_max_c: float | None
    temperatura_min_c: float | None
    precipitacion_mm: float | None
    probabilidad_lluvia_pct: float | None
    humedad_media_pct: float | None


class Pronostico(BaseModel):
    ubicacion: Ubicacion
    dias: list[DiaPronostico]
    fuente: str


logger = logging.getLogger(__name__)

# Las coordenadas de una ciudad no cambian: se recuerdan durante la vida del proceso.
_ubicaciones: dict[str, Ubicacion] = {}


def _normalizar_ciudad(ciudad: str) -> str:
    nombre = " ".join(ciudad.split())
    if len(nombre) < 2 or len(nombre) > MAX_LARGO_CIUDAD:
        raise ClimaNoDisponible("Escribe el nombre de una ciudad o municipio de Colombia.")
    return nombre


async def _get_json(cliente: httpx.AsyncClient, url: str, params: dict) -> dict:
    for intento in range(1, INTENTOS_CONEXION + 1):
        try:
            respuesta = await cliente.get(url, params=params, timeout=TIEMPO_ESPERA_SEGUNDOS)
            respuesta.raise_for_status()
            return respuesta.json()
        except httpx.TransportError as exc:
            # La primera resolución DNS tras arrancar el servidor puede fallar; se reintenta una vez.
            logger.warning("Fallo de conexión con Open-Meteo (%s), intento %d: %r", url, intento, exc)
            error = exc
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("Respuesta inválida de Open-Meteo (%s): %r", url, exc)
            error = exc
            break
    raise ClimaNoDisponible("Open-Meteo no respondió; intenta de nuevo más tarde.") from error


async def buscar_ubicacion(cliente: httpx.AsyncClient, ciudad: str) -> Ubicacion:
    nombre = _normalizar_ciudad(ciudad)
    clave = nombre.casefold()
    if clave in _ubicaciones:
        return _ubicaciones[clave]

    datos = await _get_json(
        cliente,
        GEOCODING_URL,
        {"name": nombre, "count": 1, "language": "es", "countryCode": PAIS},
    )
    resultados = datos.get("results") or []
    if not resultados:
        raise ClimaNoDisponible(f"No encontramos «{nombre}» entre las ciudades de Colombia.")
    lugar = resultados[0]
    try:
        ubicacion = Ubicacion(
            nombre=lugar["name"],
            departamento=lugar.get("admin1"),
            pais=lugar.get("country", "Colombia"),
            latitud=lugar["latitude"],
            longitud=lugar["longitude"],
            elevacion_m=lugar.get("elevation"),
        )
    except (KeyError, ValidationError) as exc:
        raise ClimaNoDisponible("Open-Meteo devolvió datos incompletos.") from exc
    _ubicaciones[clave] = ubicacion
    return ubicacion


async def clima_actual(cliente: httpx.AsyncClient, ciudad: str) -> ClimaActual:
    ubicacion = await buscar_ubicacion(cliente, ciudad)
    datos = await _get_json(
        cliente,
        FORECAST_URL,
        {
            "latitude": ubicacion.latitud,
            "longitude": ubicacion.longitud,
            "current": "temperature_2m,relative_humidity_2m,precipitation",
            "timezone": "auto",
        },
    )
    actual = datos.get("current") or {}
    try:
        return ClimaActual(
            ubicacion=ubicacion,
            hora_local=actual["time"],
            temperatura_c=actual["temperature_2m"],
            humedad_relativa_pct=actual["relative_humidity_2m"],
            precipitacion_mm=actual["precipitation"],
            fuente=FUENTE,
        )
    except (KeyError, ValidationError) as exc:
        raise ClimaNoDisponible("Open-Meteo devolvió datos incompletos.") from exc


async def pronostico(cliente: httpx.AsyncClient, ciudad: str, dias: int = 3) -> Pronostico:
    if not 1 <= dias <= MAX_DIAS_PRONOSTICO:
        raise ClimaNoDisponible(f"El pronóstico admite entre 1 y {MAX_DIAS_PRONOSTICO} días.")
    ubicacion = await buscar_ubicacion(cliente, ciudad)
    datos = await _get_json(
        cliente,
        FORECAST_URL,
        {
            "latitude": ubicacion.latitud,
            "longitude": ubicacion.longitud,
            "daily": ",".join([
                "temperature_2m_max",
                "temperature_2m_min",
                "precipitation_sum",
                "precipitation_probability_max",
                "relative_humidity_2m_mean",
            ]),
            "timezone": "auto",
            "forecast_days": dias,
        },
    )
    diario = datos.get("daily") or {}
    try:
        filas = zip(
            diario["time"],
            diario["temperature_2m_max"],
            diario["temperature_2m_min"],
            diario["precipitation_sum"],
            diario["precipitation_probability_max"],
            diario["relative_humidity_2m_mean"],
            strict=True,
        )
        return Pronostico(
            ubicacion=ubicacion,
            dias=[
                DiaPronostico(
                    fecha=fecha,
                    temperatura_max_c=maxima,
                    temperatura_min_c=minima,
                    precipitacion_mm=lluvia,
                    probabilidad_lluvia_pct=probabilidad,
                    humedad_media_pct=humedad,
                )
                for fecha, maxima, minima, lluvia, probabilidad, humedad in filas
            ],
            fuente=FUENTE,
        )
    except (KeyError, ValueError) as exc:
        raise ClimaNoDisponible("Open-Meteo devolvió datos incompletos.") from exc
