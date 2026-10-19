from __future__ import annotations

import hashlib
import os
import warnings
from contextlib import asynccontextmanager
from io import BytesIO
from pathlib import Path
from typing import Literal

import torch
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, model_validator
from PIL import Image, ImageOps, UnidentifiedImageError

from src.common import ROOT, load_checkpoint, transform
from src.domain_guard import DomainGuard, mobilenet_logits_and_embedding

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
    "No se pudo confirmar que la imagen corresponda a una hoja de café. "
    "Carga una fotografía de una sola hoja de café."
)
OUTSIDE_DOMAIN_ANALYZED_MESSAGE = (
    "No se pudo confirmar que la imagen corresponda a una hoja de café. "
    "Esta comparación se muestra porque elegiste analizarla de todos modos "
    "y solo distingue hoja sana, roya y daño por ácaro rojo."
)


class ClassScore(BaseModel):
    category: str
    label: str
    score: float = Field(ge=0.0, le=1.0)


class PredictionResponse(BaseModel):
    status: Literal[
        "classified",
        "uncertain",
        "outside_domain",
        "outside_domain_analyzed",
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
        has_result = self.status != "outside_domain"
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

        if not has_result or not result_fields_are_present:
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

        if self.status == "outside_domain_analyzed":
            if (
                self.is_supported_image
                or self.domain_score >= self.domain_threshold
                or not self.message
            ):
                raise ValueError("La comparación limitada debe conservar el rechazo de dominio")
            return self

        if (
            not self.is_supported_image
            or self.domain_score < self.domain_threshold
            or self.message is not None
            or self.status != ("uncertain" if self.is_uncertain else "classified")
        ):
            raise ValueError("La clasificación normal contradice el estado de dominio")
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

    def predict(
        self,
        image: Image.Image,
        *,
        analyze_outside_domain: bool = False,
    ) -> PredictionResponse:
        tensor = self.preprocess(image).unsqueeze(0)
        with torch.inference_mode():
            logits, embedding = mobilenet_logits_and_embedding(self.model, tensor)
            domain_score = float(self.domain_guard.scores(embedding)[0])

        outside_domain = domain_score < self.domain_guard.threshold
        if outside_domain and not analyze_outside_domain:
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
            status=(
                "outside_domain_analyzed"
                if outside_domain
                else "uncertain" if best_score < UNCERTAINTY_THRESHOLD else "classified"
            ),
            is_supported_image=not outside_domain,
            domain_score=domain_score,
            domain_threshold=self.domain_guard.threshold,
            message=OUTSIDE_DOMAIN_ANALYZED_MESSAGE if outside_domain else None,
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
    yield


app = FastAPI(
    title="CaféIA API",
    description="API de apoyo para clasificación visual de hojas de café en tres categorías.",
    version="0.2.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins(),
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


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


@app.post("/predict", response_model=PredictionResponse)
async def predict(
    request: Request,
    file: UploadFile = File(...),
    analyze_outside_domain: bool = Form(False),
) -> PredictionResponse:
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

    image = _decode_image(data, ALLOWED_EXTENSIONS[extension])
    predictor: Predictor = request.app.state.predictor
    return predictor.predict(
        image,
        analyze_outside_domain=analyze_outside_domain,
    )
