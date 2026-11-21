from __future__ import annotations

import base64
import hashlib
import os
import warnings
from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING, Literal

import anyio
import httpx2 as httpx
import torch
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from mcp import Client
from mcp_types import CallToolResult
from pydantic import BaseModel, Field, ValidationError, model_validator
from PIL import Image, ImageOps, UnidentifiedImageError

from backend.clima import CIUDAD_PREDETERMINADA, MAX_LARGO_CIUDAD, ClimaActual, Pronostico
from src.common import ROOT, load_checkpoint, transform
from src.domain_guard import DomainGuard, mobilenet_logits_and_embedding

if TYPE_CHECKING:
    from mcp.server.mcpserver import MCPServer

MAX_FILE_SIZE = 10 * 1024 * 1024
READ_CHUNK_SIZE = 1024 * 1024
UNCERTAINTY_THRESHOLD = 0.70
ALLOWED_EXTENSIONS = {".jpg": "JPEG", ".jpeg": "JPEG", ".png": "PNG"}
ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png"}
CLASS_NAMES = {
    "coffee___healthy": "Hoja sana",
    "coffee___rust": "Roya",
    "coffee___red_spider_mite": "Ácaro rojo",
}
EXPECTED_CLASS_ORDER = [
    "coffee___healthy",
    "coffee___red_spider_mite",
    "coffee___rust",
]
DEFAULT_ALLOWED_ORIGINS = ("http://localhost:3000", "http://127.0.0.1:3000")
OUTSIDE_DOMAIN_MESSAGE = (
    "No pudimos confirmar que la imagen corresponda a una hoja de café que "
    "CaféIA pueda analizar. Carga una fotografía clara de una sola hoja de café."
)
DIAS_PRONOSTICO_AGENTE = 3
TIEMPO_MAXIMO_CLIMA_SEGUNDOS = 15.0
CLIMA_OMITIDO_MESSAGE = "El agente no consultó el clima porque la imagen fue rechazada."


class ClassScore(BaseModel):
    category: str
    label: str
    score: float = Field(ge=0.0, le=1.0)


class PredictionResponse(BaseModel):
    status: Literal[
        "classified",
        "uncertain",
        "outside_domain",
    ]
    is_supported_image: bool
    domain_score: float = Field(ge=-1.0, le=1.0)
    domain_threshold: float = Field(ge=-1.0, le=1.0)
    message: str | None = None
    category: str | None = None
    category_label: str | None = None
    score: float | None = None
    scores: list[ClassScore] = Field(default_factory=list)
    is_uncertain: bool
    uncertainty_threshold: float = Field(ge=0.0, le=1.0)

    @model_validator(mode="after")
    def validate_response_contract(self) -> "PredictionResponse":
        result_fields_are_present = (
            self.category is not None
            and self.category_label is not None
            and self.score is not None
            and len(self.scores) == len(EXPECTED_CLASS_ORDER)
        )

        if self.status == "outside_domain":
            if (
                self.is_supported_image
                or self.domain_score >= self.domain_threshold
                or not self.message
                or self.category is not None
                or self.category_label is not None
                or self.score is not None
                or self.scores
                or not self.is_uncertain
                or self.uncertainty_threshold != UNCERTAINTY_THRESHOLD
            ):
                raise ValueError("Una imagen fuera del dominio no puede exponer una clasificación")
            return self

        if not result_fields_are_present:
            raise ValueError("La respuesta de clasificación está incompleta")
        if self.uncertainty_threshold != UNCERTAINTY_THRESHOLD:
            raise ValueError("El umbral de incertidumbre no coincide con el configurado")

        returned_categories = [item.category for item in self.scores]
        if returned_categories != EXPECTED_CLASS_ORDER:
            raise ValueError("Las puntuaciones no respetan el orden de clases")
        if any(item.label != CLASS_NAMES[item.category] for item in self.scores):
            raise ValueError("Una etiqueta legible no coincide con su categoría")

        score_by_category = {item.category: item.score for item in self.scores}
        if self.category not in score_by_category:
            raise ValueError("La categoría seleccionada no aparece en las puntuaciones")
        if self.category_label != CLASS_NAMES[self.category]:
            raise ValueError("La etiqueta seleccionada no coincide con la categoría")
        if abs(sum(score_by_category.values()) - 1.0) > 1e-5:
            raise ValueError("Las puntuaciones no suman uno")

        selected_score = score_by_category[self.category]
        maximum_score = max(score_by_category.values())
        if (
            self.score is None
            or abs(self.score - selected_score) > 1e-7
            or abs(self.score - maximum_score) > 1e-7
        ):
            raise ValueError("La categoría seleccionada no coincide con la puntuación mayor")
        if self.is_uncertain != (self.score < self.uncertainty_threshold):
            raise ValueError("El estado de incertidumbre no coincide con la puntuación")

        if (
            not self.is_supported_image
            or self.domain_score < self.domain_threshold
            or self.message is not None
            or self.status != ("uncertain" if self.is_uncertain else "classified")
        ):
            raise ValueError("La clasificación normal contradice el estado de dominio")
        return self


class PasoAgente(BaseModel):
    servidor: str
    herramienta: str
    estado: Literal["ok", "error", "omitida"]
    detalle: str | None = None


class ClimaDelAnalisis(BaseModel):
    actual: ClimaActual
    pronostico: Pronostico


class AnalisisResponse(BaseModel):
    prediccion: PredictionResponse
    clima: ClimaDelAnalisis | None = None
    clima_mensaje: str | None = None
    pasos: list[PasoAgente]

    @model_validator(mode="after")
    def validate_climate_message(self) -> "AnalisisResponse":
        if (self.clima is None) == (self.clima_mensaje is None):
            raise ValueError("El análisis debe traer el clima o explicar por qué no lo trae")
        return self


class HealthResponse(BaseModel):
    status: str
    model_loaded: bool
    model: str
    model_id: str
    checkpoint_sha256: str
    domain_guard_loaded: bool
    domain_guard_sha256: str
    domain_guard_method: str
    domain_threshold: float
    selected_epoch: int | None
    uncertainty_threshold: float
    classes: list[str]


class Predictor:
    def __init__(
        self,
        checkpoint_path: Path,
        expected_sha256: str,
        model_id: str,
        domain_guard_path: Path,
        expected_domain_guard_sha256: str,
    ) -> None:
        self.checkpoint_sha256 = _sha256_file(checkpoint_path)
        if self.checkpoint_sha256 != expected_sha256:
            raise RuntimeError(
                "El SHA256 del checkpoint no coincide con MODEL_SHA256: "
                f"esperado {expected_sha256}, obtenido {self.checkpoint_sha256}"
            )
        self.model, self.checkpoint = load_checkpoint(checkpoint_path)
        self.model_id = model_id
        self.classes: list[str] = self.checkpoint["classes"]
        if self.classes != EXPECTED_CLASS_ORDER:
            raise ValueError(
                "Orden de clases incompatible: "
                f"{self.classes}; esperado {EXPECTED_CLASS_ORDER}"
            )
        # Es exactamente la transformación de inferencia definida en src/common.py.
        self.preprocess = transform(training=False)
        self.domain_guard_sha256 = _sha256_file(domain_guard_path)
        if self.domain_guard_sha256 != expected_domain_guard_sha256:
            raise RuntimeError(
                "El SHA256 del filtro de dominio no coincide con DOMAIN_GUARD_SHA256: "
                f"esperado {expected_domain_guard_sha256}, obtenido {self.domain_guard_sha256}"
            )
        self.domain_guard = DomainGuard.load(domain_guard_path)
        guard_checkpoint_sha256 = self.domain_guard.metadata.get("checkpoint_sha256")
        if guard_checkpoint_sha256 != self.checkpoint_sha256:
            raise RuntimeError(
                "El filtro de dominio fue construido con un checkpoint diferente: "
                f"{guard_checkpoint_sha256}"
            )
        guard_classes = self.domain_guard.metadata.get("classes")
        if guard_classes != self.classes:
            raise RuntimeError(
                "El orden de clases del filtro de dominio no coincide con el checkpoint"
            )
        guard_manifest_sha256 = self.domain_guard.metadata.get("manifest_sha256")
        if guard_manifest_sha256 != self.checkpoint.get("manifest_sha256"):
            raise RuntimeError(
                "El filtro de dominio y el checkpoint no corresponden al mismo manifiesto"
            )
        expected_embedding_size = self.model.classifier[0].out_features
        if self.domain_guard.reference_embeddings.shape[1] != expected_embedding_size:
            raise RuntimeError(
                "La dimensión del filtro de dominio no es compatible con MobileNet"
            )
        self.domain_guard_method = str(self.domain_guard.metadata.get("method", "unknown"))

    def predict(self, image: Image.Image) -> PredictionResponse:
        tensor = self.preprocess(image).unsqueeze(0)
        with torch.inference_mode():
            logits, embedding = mobilenet_logits_and_embedding(self.model, tensor)
            domain_score = float(self.domain_guard.scores(embedding)[0])

        outside_domain = domain_score < self.domain_guard.threshold
        if outside_domain:
            return PredictionResponse(
                status="outside_domain",
                is_supported_image=False,
                domain_score=domain_score,
                domain_threshold=self.domain_guard.threshold,
                message=OUTSIDE_DOMAIN_MESSAGE,
                is_uncertain=True,
                uncertainty_threshold=UNCERTAINTY_THRESHOLD,
            )

        probabilities = torch.softmax(logits, dim=1)[0].tolist()

        best_index = max(range(len(probabilities)), key=probabilities.__getitem__)
        best_score = float(probabilities[best_index])
        best_category = self.classes[best_index]
        scores = [
            ClassScore(category=category, label=CLASS_NAMES[category], score=float(probabilities[index]))
            for index, category in enumerate(self.classes)
        ]
        return PredictionResponse(
            status="uncertain" if best_score < UNCERTAINTY_THRESHOLD else "classified",
            is_supported_image=True,
            domain_score=domain_score,
            domain_threshold=self.domain_guard.threshold,
            message=None,
            category=best_category,
            category_label=CLASS_NAMES[best_category],
            score=best_score,
            scores=scores,
            is_uncertain=best_score < UNCERTAINTY_THRESHOLD,
            uncertainty_threshold=UNCERTAINTY_THRESHOLD,
        )


def _checkpoint_path() -> Path:
    configured = Path(os.getenv("MODEL_PATH", "models/mobilenet_finetuned_epoch6.pt"))
    return configured if configured.is_absolute() else ROOT / configured


def _domain_guard_path() -> Path:
    configured = Path(os.getenv("DOMAIN_GUARD_PATH", "models/coffee_domain_guard.pt"))
    return configured if configured.is_absolute() else ROOT / configured


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _expected_sha256(environment_variable: str) -> str:
    expected = os.getenv(environment_variable, "").strip().lower()
    if len(expected) != 64 or any(character not in "0123456789abcdef" for character in expected):
        raise RuntimeError(
            f"{environment_variable} debe contener un SHA256 hexadecimal de 64 caracteres"
        )
    return expected


def _model_id() -> str:
    model_id = os.getenv("MODEL_ID", "").strip()
    if not model_id:
        raise RuntimeError("MODEL_ID debe identificar el checkpoint desplegado")
    return model_id


def _allowed_origins() -> list[str]:
    configured = os.getenv("CORS_ALLOWED_ORIGINS")
    origins = list(DEFAULT_ALLOWED_ORIGINS) if configured is None else [
        origin.strip().rstrip("/") for origin in configured.split(",") if origin.strip()
    ]
    if not origins:
        raise RuntimeError("CORS_ALLOWED_ORIGINS debe contener al menos un origen")
    if "*" in origins:
        raise RuntimeError("CORS_ALLOWED_ORIGINS no admite '*'; usa orígenes explícitos")
    if any(not origin.startswith(("http://", "https://")) for origin in origins):
        raise RuntimeError("Cada origen CORS debe empezar por http:// o https://")
    return origins


@dataclass(frozen=True)
class ServidoresMCP:
    clasificador: MCPServer
    clima: MCPServer


@asynccontextmanager
async def iniciar_mcp(app: FastAPI, cliente_http: httpx.AsyncClient) -> AsyncIterator[None]:
    """Crea los dos servidores MCP y deja listas sus rutas HTTP.

    Se crean en cada arranque porque el gestor HTTP de cada servidor solo puede
    iniciarse una vez. El clasificador lee el predictor de ``app.state`` en cada
    llamada, así que usa exactamente el mismo modelo que ``/predict``.
    """
    # Importación diferida: mcp_servidores importa los modelos de este módulo.
    from backend.mcp_servidores import (
        aplicacion_http,
        crear_servidor_clasificador,
        crear_servidor_clima,
    )

    servidores = ServidoresMCP(
        clasificador=crear_servidor_clasificador(lambda: app.state.predictor),
        clima=crear_servidor_clima(cliente_http),
    )
    aplicaciones = {
        "clasificador": aplicacion_http(servidores.clasificador),
        "clima": aplicacion_http(servidores.clima),
    }
    async with AsyncExitStack() as pila:
        for servidor in (servidores.clasificador, servidores.clima):
            await pila.enter_async_context(servidor.session_manager.run())
        app.state.mcp = servidores
        app.state.mcp_http = aplicaciones
        try:
            yield
        finally:
            del app.state.mcp, app.state.mcp_http


@asynccontextmanager
async def lifespan(app: FastAPI):
    checkpoint_path = _checkpoint_path()
    if not checkpoint_path.is_file():
        raise FileNotFoundError(f"No se encontró el checkpoint: {checkpoint_path}")
    domain_guard_path = _domain_guard_path()
    if not domain_guard_path.is_file():
        raise FileNotFoundError(f"No se encontró el filtro de dominio: {domain_guard_path}")
    app.state.predictor = Predictor(
        checkpoint_path=checkpoint_path,
        expected_sha256=_expected_sha256("MODEL_SHA256"),
        model_id=_model_id(),
        domain_guard_path=domain_guard_path,
        expected_domain_guard_sha256=_expected_sha256("DOMAIN_GUARD_SHA256"),
    )
    async with httpx.AsyncClient(headers={"User-Agent": "CafeIA/0.4"}) as cliente_http:
        async with iniciar_mcp(app, cliente_http):
            yield


class _PuertaMCP:
    """Entrega las solicitudes HTTP al servidor MCP creado en el arranque."""

    def __init__(self, nombre: str) -> None:
        self.nombre = nombre

    async def __call__(self, scope, receive, send) -> None:
        aplicacion = getattr(scope["app"].state, "mcp_http", {}).get(self.nombre)
        if aplicacion is None:
            respuesta = JSONResponse({"detail": "Servidor MCP no disponible."}, status_code=503)
            await respuesta(scope, receive, send)
            return
        await aplicacion(scope, receive, send)


app = FastAPI(
    title="CaféIA API",
    description=(
        "API de apoyo para clasificación visual de hojas de café en tres categorías. "
        "Publica dos servidores MCP: /clasificador/mcp y /clima/mcp."
    ),
    version="0.4.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins(),
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)
app.mount("/clasificador", _PuertaMCP("clasificador"))
app.mount("/clima", _PuertaMCP("clima"))


async def _read_upload(upload: UploadFile) -> bytes:
    data = bytearray()
    while chunk := await upload.read(READ_CHUNK_SIZE):
        data.extend(chunk)
        if len(data) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=413,
                detail="La fotografía supera el tamaño máximo de 10 MB.",
            )
    if not data:
        raise HTTPException(status_code=400, detail="El archivo está vacío.")
    return bytes(data)


def _decode_image(data: bytes, expected_format: str) -> Image.Image:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(data)) as candidate:
                actual_format = candidate.format
                candidate.verify()
            if actual_format != expected_format:
                raise HTTPException(
                    status_code=415,
                    detail=f"El contenido no corresponde al formato {expected_format} indicado.",
                )
            with Image.open(BytesIO(data)) as candidate:
                return ImageOps.exif_transpose(candidate).convert("RGB")
    except HTTPException:
        raise
    except (
        UnidentifiedImageError,
        OSError,
        SyntaxError,
        ValueError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ) as exc:
        raise HTTPException(status_code=400, detail="El archivo no contiene una imagen JPG o PNG válida.") from exc


@app.get("/health", response_model=HealthResponse)
def health(request: Request) -> HealthResponse:
    predictor: Predictor = request.app.state.predictor
    return HealthResponse(
        status="ok",
        model_loaded=True,
        model=predictor.checkpoint["model"],
        model_id=predictor.model_id,
        checkpoint_sha256=predictor.checkpoint_sha256,
        domain_guard_loaded=True,
        domain_guard_sha256=predictor.domain_guard_sha256,
        domain_guard_method=predictor.domain_guard_method,
        domain_threshold=predictor.domain_guard.threshold,
        selected_epoch=predictor.checkpoint.get("selected_candidate_epoch"),
        uncertainty_threshold=UNCERTAINTY_THRESHOLD,
        classes=predictor.classes,
    )


async def _read_photo(file: UploadFile) -> tuple[bytes, str, Image.Image]:
    """Valida extensión, tipo, tamaño y contenido; devuelve bytes, formato e imagen."""
    filename = file.filename or ""
    extension = Path(filename).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        await file.close()
        raise HTTPException(status_code=415, detail="Solo se permiten archivos .jpg, .jpeg o .png.")
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        await file.close()
        raise HTTPException(status_code=415, detail="El tipo de contenido debe ser image/jpeg o image/png.")

    try:
        data = await _read_upload(file)
    finally:
        await file.close()

    image_format = ALLOWED_EXTENSIONS[extension]
    return data, image_format, _decode_image(data, image_format)


@app.post("/predict", response_model=PredictionResponse)
async def predict(
    request: Request,
    file: UploadFile = File(...),
) -> PredictionResponse:
    _, _, image = await _read_photo(file)
    predictor: Predictor = request.app.state.predictor
    return predictor.predict(image)


def _tool_error_text(result: CallToolResult) -> str:
    text = " ".join(block.text for block in result.content if block.type == "text").strip()
    # MCPServer antepone "Error executing tool <nombre>: " al mensaje de la herramienta.
    prefix, separator, message = text.partition(": ")
    if separator and prefix.startswith("Error executing tool"):
        return message
    return text or "La herramienta no devolvió detalles."


async def _consult_climate(
    servidor: MCPServer,
    ciudad: str,
    pasos: list[PasoAgente],
) -> tuple[ClimaDelAnalisis | None, str | None]:
    nombre = "cafeia-clima"
    try:
        with anyio.fail_after(TIEMPO_MAXIMO_CLIMA_SEGUNDOS):
            async with Client(servidor, mode="legacy") as cliente:
                actual = await cliente.call_tool("clima_actual", {"ciudad": ciudad})
                if actual.is_error:
                    mensaje = _tool_error_text(actual)
                    pasos.append(PasoAgente(servidor=nombre, herramienta="clima_actual", estado="error", detalle=mensaje))
                    pasos.append(PasoAgente(servidor=nombre, herramienta="pronostico", estado="omitida",
                                            detalle="No se consultó porque falló el clima actual."))
                    return None, mensaje
                pasos.append(PasoAgente(servidor=nombre, herramienta="clima_actual", estado="ok"))

                pronostico = await cliente.call_tool(
                    "pronostico", {"ciudad": ciudad, "dias": DIAS_PRONOSTICO_AGENTE}
                )
                if pronostico.is_error:
                    mensaje = _tool_error_text(pronostico)
                    pasos.append(PasoAgente(servidor=nombre, herramienta="pronostico", estado="error", detalle=mensaje))
                    return None, mensaje
                pasos.append(PasoAgente(servidor=nombre, herramienta="pronostico", estado="ok"))
                return ClimaDelAnalisis(
                    actual=ClimaActual.model_validate(actual.structured_content),
                    pronostico=Pronostico.model_validate(pronostico.structured_content),
                ), None
    except TimeoutError:
        mensaje = "El servicio de clima tardó demasiado en responder."
    except ValidationError:
        mensaje = "El servicio de clima devolvió datos incompletos."
    pasos.append(PasoAgente(servidor=nombre, herramienta="clima", estado="error", detalle=mensaje))
    return None, mensaje


@app.post("/analizar", response_model=AnalisisResponse)
async def analizar(
    request: Request,
    file: UploadFile = File(...),
    ciudad: str = Form(CIUDAD_PREDETERMINADA, max_length=MAX_LARGO_CIUDAD),
) -> AnalisisResponse:
    """Agente CaféIA: consulta sus dos sensores a través de un cliente MCP.

    Regla del agente: siempre usa el sensor visual; solo consulta el sensor
    ambiental si la imagen fue aceptada como una hoja de café analizable.
    """
    data, image_format, _ = await _read_photo(file)
    servidores: ServidoresMCP = request.app.state.mcp
    pasos: list[PasoAgente] = []

    async with Client(servidores.clasificador, mode="legacy") as cliente:
        resultado = await cliente.call_tool(
            "clasificar_hoja",
            {
                "imagen_base64": base64.b64encode(data).decode("ascii"),
                "formato": image_format.lower(),
            },
        )
    if resultado.is_error:
        # La imagen ya fue validada arriba; un error aquí es interno y no se detalla.
        raise HTTPException(status_code=502, detail="El sensor de clasificación no pudo analizar la fotografía.")
    prediccion = PredictionResponse.model_validate(resultado.structured_content)
    pasos.append(PasoAgente(servidor="cafeia-clasificador", herramienta="clasificar_hoja", estado="ok"))

    if prediccion.status == "outside_domain":
        pasos.append(PasoAgente(servidor="cafeia-clima", herramienta="clima_actual", estado="omitida",
                                detalle=CLIMA_OMITIDO_MESSAGE))
        return AnalisisResponse(prediccion=prediccion, clima_mensaje=CLIMA_OMITIDO_MESSAGE, pasos=pasos)

    clima, clima_mensaje = await _consult_climate(servidores.clima, ciudad, pasos)
    return AnalisisResponse(prediccion=prediccion, clima=clima, clima_mensaje=clima_mensaje, pasos=pasos)
