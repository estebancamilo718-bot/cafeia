from __future__ import annotations

import hashlib
import os
import warnings
from contextlib import asynccontextmanager
from io import BytesIO
from pathlib import Path

import torch
from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from PIL import Image, ImageOps, UnidentifiedImageError

from src.common import ROOT, load_checkpoint, transform

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


class ClassScore(BaseModel):
    category: str
    label: str
    score: float


class PredictionResponse(BaseModel):
    category: str
    category_label: str
    score: float
    scores: list[ClassScore]
    is_uncertain: bool
    uncertainty_threshold: float


class HealthResponse(BaseModel):
    status: str
    model_loaded: bool
    model: str
    model_id: str
    checkpoint_sha256: str
    selected_epoch: int | None
    uncertainty_threshold: float
    classes: list[str]


class Predictor:
    def __init__(self, checkpoint_path: Path, expected_sha256: str, model_id: str) -> None:
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

    def predict(self, image: Image.Image) -> PredictionResponse:
        tensor = self.preprocess(image).unsqueeze(0)
        with torch.inference_mode():
            probabilities = torch.softmax(self.model(tensor), dim=1)[0].tolist()

        best_index = max(range(len(probabilities)), key=probabilities.__getitem__)
        best_score = float(probabilities[best_index])
        best_category = self.classes[best_index]
        scores = [
            ClassScore(category=category, label=CLASS_NAMES[category], score=float(probabilities[index]))
            for index, category in enumerate(self.classes)
        ]
        return PredictionResponse(
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


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _expected_model_sha256() -> str:
    expected = os.getenv("MODEL_SHA256", "").strip().lower()
    if len(expected) != 64 or any(character not in "0123456789abcdef" for character in expected):
        raise RuntimeError("MODEL_SHA256 debe contener un SHA256 hexadecimal de 64 caracteres")
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
    app.state.predictor = Predictor(
        checkpoint_path=checkpoint_path,
        expected_sha256=_expected_model_sha256(),
        model_id=_model_id(),
    )
    yield


app = FastAPI(
    title="CaféIA API",
    description="API local del prototipo académico de clasificación de hojas de café.",
    version="0.1.0",
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
        selected_epoch=predictor.checkpoint.get("selected_candidate_epoch"),
        uncertainty_threshold=UNCERTAINTY_THRESHOLD,
        classes=predictor.classes,
    )


@app.post("/predict", response_model=PredictionResponse)
async def predict(request: Request, file: UploadFile = File(...)) -> PredictionResponse:
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
    return predictor.predict(image)
