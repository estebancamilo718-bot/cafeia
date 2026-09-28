from __future__ import annotations

from contextlib import asynccontextmanager
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from PIL import Image

import backend.main as api


class FakePredictor:
    """Doble determinista: prueba el contrato HTTP, no el modelo."""

    checkpoint_sha256 = "0" * 64
    model_id = "fake-predictor"
    classes = api.EXPECTED_CLASS_ORDER
    checkpoint = {"model": "mobilenet", "selected_candidate_epoch": 6}

    def predict(self, image: Image.Image) -> api.PredictionResponse:
        assert image.mode == "RGB"
        return api.PredictionResponse(
            category="coffee___healthy",
            category_label="Hoja sana",
            score=0.8,
            scores=[
                api.ClassScore(category="coffee___healthy", label="Hoja sana", score=0.8),
                api.ClassScore(
                    category="coffee___red_spider_mite",
                    label="Ácaro rojo",
                    score=0.1,
                ),
                api.ClassScore(category="coffee___rust", label="Roya", score=0.1),
            ],
            is_uncertain=False,
            uncertainty_threshold=api.UNCERTAINTY_THRESHOLD,
        )


class FailingPredictor(FakePredictor):
    def predict(self, image: Image.Image) -> api.PredictionResponse:
        raise RuntimeError("detalle interno que no debe exponerse")


@asynccontextmanager
async def fake_lifespan(app):
    app.state.predictor = FakePredictor()
    yield


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(api.app.router, "lifespan_context", fake_lifespan)
    with TestClient(api.app, raise_server_exceptions=False) as test_client:
        yield test_client


def image_bytes(image_format: str) -> bytes:
    output = BytesIO()
    Image.new("RGB", (32, 24), (72, 112, 65)).save(output, format=image_format)
    return output.getvalue()


def test_health_contract_uses_injected_predictor(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "model_loaded": True,
        "model": "mobilenet",
        "model_id": "fake-predictor",
        "checkpoint_sha256": "0" * 64,
        "selected_epoch": 6,
        "uncertainty_threshold": 0.7,
        "classes": api.EXPECTED_CLASS_ORDER,
    }


def test_predict_contract_with_valid_jpeg(client: TestClient) -> None:
    response = client.post(
        "/predict",
        files={"file": ("hoja.jpg", image_bytes("JPEG"), "image/jpeg")},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["category"] == "coffee___healthy"
    assert payload["category_label"] == "Hoja sana"
    assert payload["score"] == 0.8
    assert payload["is_uncertain"] is False
    assert payload["uncertainty_threshold"] == 0.7
    assert [item["category"] for item in payload["scores"]] == api.EXPECTED_CLASS_ORDER
    assert sum(item["score"] for item in payload["scores"]) == pytest.approx(1.0)


@pytest.mark.parametrize(
    ("filename", "content_type", "content", "expected_status"),
    [
        ("hoja.gif", "image/gif", b"GIF89a", 415),
        ("hoja.jpg", "text/plain", image_bytes("JPEG"), 415),
        ("hoja.jpg", "image/jpeg", b"", 400),
        ("hoja.jpg", "image/jpeg", b"no es una imagen", 400),
        ("hoja.png", "image/png", image_bytes("JPEG"), 415),
    ],
)
def test_rejects_invalid_uploads(
    client: TestClient,
    filename: str,
    content_type: str,
    content: bytes,
    expected_status: int,
) -> None:
    response = client.post(
        "/predict",
        files={"file": (filename, content, content_type)},
    )

    assert response.status_code == expected_status
    assert isinstance(response.json()["detail"], str)


def test_rejects_file_larger_than_ten_megabytes(client: TestClient) -> None:
    response = client.post(
        "/predict",
        files={
            "file": (
                "hoja.jpg",
                b"0" * (api.MAX_FILE_SIZE + 1),
                "image/jpeg",
            )
        },
    )

    assert response.status_code == 413
    assert response.json()["detail"] == "La fotografía supera el tamaño máximo de 10 MB."


def test_internal_prediction_error_is_not_exposed(client: TestClient) -> None:
    client.app.state.predictor = FailingPredictor()

    response = client.post(
        "/predict",
        files={"file": ("hoja.jpg", image_bytes("JPEG"), "image/jpeg")},
    )

    assert response.status_code == 500
    assert "detalle interno" not in response.text
