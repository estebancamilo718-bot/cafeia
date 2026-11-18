"""Servidores MCP de CaféIA: los dos sensores del agente.

- ``cafeia-clasificador`` (sensor visual): expone el MobileNet ya cargado por el
  backend, con el mismo filtro de dominio y el mismo umbral que ``/predict``.
- ``cafeia-clima`` (sensor ambiental): consulta Open-Meteo.

El backend los usa a través de un cliente MCP (ver ``backend/main.py``) y además
los publica por HTTP en ``/clasificador/mcp`` y ``/clima/mcp`` para que cualquier
cliente MCP, como MCP Inspector, pueda descubrirlos y llamarlos.
"""

from __future__ import annotations

import base64
import binascii
import logging
import os
from collections.abc import Callable
from typing import Annotated, Literal

import httpx2 as httpx
from fastapi import HTTPException
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.server.transport_security import TransportSecuritySettings
from pydantic import BaseModel, Field
from starlette.applications import Starlette

from backend import clima
from backend.main import (
    CLASS_NAMES,
    MAX_FILE_SIZE,
    UNCERTAINTY_THRESHOLD,
    PredictionResponse,
    Predictor,
    _decode_image,
)

NOMBRE_CLASIFICADOR = "cafeia-clasificador"
NOMBRE_CLIMA = "cafeia-clima"
FORMATOS = {"jpeg": "JPEG", "png": "PNG"}
# Base64 ocupa 4/3 del archivo original; se admite el mismo límite de 10 MB que /predict.
MAX_LARGO_BASE64 = (MAX_FILE_SIZE + 2) // 3 * 4
MAX_CUERPO_HTTP_MCP = MAX_LARGO_BASE64 + 64 * 1024
HOSTS_PREDETERMINADOS = (
    "127.0.0.1",
    "127.0.0.1:*",
    "localhost",
    "localhost:*",
    "[::1]:*",
    "cafeia-jiwk.onrender.com",
)

logger = logging.getLogger(__name__)


class EstadoModelo(BaseModel):
    modelo: str
    model_id: str
    checkpoint_sha256: str
    clases: list[str]
    etiquetas: list[str]
    umbral_incertidumbre: float
    umbral_dominio: float


def crear_servidor_clasificador(obtener_predictor: Callable[[], Predictor]) -> MCPServer:
    servidor = MCPServer(
        NOMBRE_CLASIFICADOR,
        title="CaféIA · Clasificador de hojas",
        instructions=(
            "Sensor visual de CaféIA. Clasifica una fotografía de una hoja de café en "
            "hoja sana, roya o ácaro rojo. Es una herramienta de apoyo, no un diagnóstico."
        ),
    )

    @servidor.tool(
        description=(
            "Clasifica una fotografía JPG o PNG de una sola hoja de café (máximo 10 MB, "
            "codificada en base64). Primero comprueba si la imagen parece una hoja que el "
            "modelo pueda analizar; si no, responde 'outside_domain' sin categoría. Si la "
            f"puntuación mayor es menor que {UNCERTAINTY_THRESHOLD:.2f}, el resultado es "
            "'uncertain' y requiere revisión humana. Las puntuaciones no son probabilidades calibradas."
        ),
    )
    def clasificar_hoja(
        imagen_base64: Annotated[str, Field(description="Contenido del archivo en base64, sin prefijo data:")],
        formato: Annotated[Literal["jpeg", "png"], Field(description="Formato real del archivo")],
    ) -> PredictionResponse:
        if len(imagen_base64) > MAX_LARGO_BASE64:
            raise ToolError("La fotografía supera el tamaño máximo de 10 MB.")
        try:
            datos = base64.b64decode(imagen_base64, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ToolError("imagen_base64 no es un texto base64 válido.") from exc
        if not datos:
            raise ToolError("El archivo está vacío.")
        try:
            imagen = _decode_image(datos, FORMATOS[formato])
        except HTTPException as exc:
            raise ToolError(str(exc.detail)) from exc
        try:
            return obtener_predictor().predict(imagen)
        except Exception as exc:
            # El detalle interno queda en el registro del servidor, no en la respuesta.
            logger.exception("Falló la clasificación solicitada por MCP")
            raise ToolError("No pudimos analizar la fotografía.") from exc

    @servidor.tool(description="Describe el modelo cargado: clases, umbrales e identificador del checkpoint.")
    def estado_modelo() -> EstadoModelo:
        predictor = obtener_predictor()
        return EstadoModelo(
            modelo=predictor.checkpoint["model"],
            model_id=predictor.model_id,
            checkpoint_sha256=predictor.checkpoint_sha256,
            clases=predictor.classes,
            etiquetas=[CLASS_NAMES[categoria] for categoria in predictor.classes],
            umbral_incertidumbre=UNCERTAINTY_THRESHOLD,
            umbral_dominio=predictor.domain_guard.threshold,
        )

    return servidor


def crear_servidor_clima(cliente_http: httpx.AsyncClient) -> MCPServer:
    servidor = MCPServer(
        NOMBRE_CLIMA,
        title="CaféIA · Clima de la zona",
        instructions=(
            "Sensor ambiental de CaféIA. Devuelve datos de Open-Meteo para ciudades y "
            "municipios de Colombia. Solo entrega datos; no estima riesgo de enfermedades."
        ),
    )

    @servidor.tool(description="Temperatura, humedad relativa y precipitación actuales de una ciudad de Colombia.")
    async def clima_actual(
        ciudad: Annotated[str, Field(description="Ciudad o municipio de Colombia")] = clima.CIUDAD_PREDETERMINADA,
    ) -> clima.ClimaActual:
        try:
            return await clima.clima_actual(cliente_http, ciudad)
        except clima.ClimaNoDisponible as exc:
            raise ToolError(str(exc)) from exc

    @servidor.tool(
        description=(
            "Pronóstico diario de una ciudad de Colombia: temperatura máxima y mínima, "
            "lluvia, probabilidad de lluvia y humedad media."
        ),
    )
    async def pronostico(
        ciudad: Annotated[str, Field(description="Ciudad o municipio de Colombia")] = clima.CIUDAD_PREDETERMINADA,
        dias: Annotated[int, Field(ge=1, le=clima.MAX_DIAS_PRONOSTICO, description="Días a consultar")] = 3,
    ) -> clima.Pronostico:
        try:
            return await clima.pronostico(cliente_http, ciudad, dias)
        except clima.ClimaNoDisponible as exc:
            raise ToolError(str(exc)) from exc

    return servidor


def _hosts_permitidos() -> list[str]:
    adicionales = [
        host.strip() for host in os.getenv("MCP_ALLOWED_HOSTS", "").split(",") if host.strip()
    ]
    return [*HOSTS_PREDETERMINADOS, *adicionales]


def aplicacion_http(servidor: MCPServer) -> Starlette:
    """Publica un servidor MCP por Streamable HTTP, sin sesiones y con respuestas JSON."""
    return servidor.streamable_http_app(
        stateless_http=True,
        json_response=True,
        max_request_body_size=MAX_CUERPO_HTTP_MCP,
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=_hosts_permitidos(),
            allowed_origins=["http://127.0.0.1:*", "http://localhost:*"],
        ),
    )
