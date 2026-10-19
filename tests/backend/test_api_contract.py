from __future__ import annotations

from contextlib import asynccontextmanager
from io import BytesIO

import pytest
import torch
from fastapi.testclient import TestClient
from PIL import Image

import backend.main as api


class FakePredictor:
    """Doble determinista: prueba el contrato HTTP, no el modelo."""

    checkpoint_sha256 = "0" * 64
    domain_guard_sha256 = "1" * 64
    domain_guard_method = "fake_cosine_guard"
    model_id = "fake-predictor"
    classes = api.EXPECTED_CLASS_ORDER
    checkpoint = {"model": "mobilenet", "selected_candidate_epoch": 6}
    domain_guard = type("FakeGuard", (), {"threshold": 0.65})()

    def predict(
        self,
        image: Image.Image,
        *,
        analyze_outside_domain: bool = False,
    ) -> api.PredictionResponse:
        assert image.mode == "RGB"
        assert analyze_outside_domain is False
        return api.PredictionResponse(
            status="classified",
            is_supported_image=True,
            domain_score=0.91,
            domain_threshold=0.65,
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


class OutsideDomainPredictor(FakePredictor):
    def predict(
        self,
        image: Image.Image,
        *,
        analyze_outside_domain: bool = False,
    ) -> api.PredictionResponse:
        if analyze_outside_domain:
            return api.PredictionResponse(
                status="outside_domain_analyzed",
                is_supported_image=False,
                domain_score=0.31,
                domain_threshold=0.65,
                message=api.OUTSIDE_DOMAIN_ANALYZED_MESSAGE,
                category="coffee___rust",
                category_label="Roya",
                score=0.6,
                scores=[
                    api.ClassScore(
                        category="coffee___healthy",
                        label="Hoja sana",
                        score=0.25,
                    ),
                    api.ClassScore(
                        category="coffee___red_spider_mite",
                        label="Ácaro rojo",
                        score=0.15,
                    ),
                    api.ClassScore(
                        category="coffee___rust",
                        label="Roya",
                        score=0.6,
                    ),
                ],
                is_uncertain=True,
                uncertainty_threshold=api.UNCERTAINTY_THRESHOLD,
            )
        return api.PredictionResponse(
            status="outside_domain",
            is_supported_image=False,
            domain_score=0.31,
            domain_threshold=0.65,
            message=api.OUTSIDE_DOMAIN_MESSAGE,
            is_uncertain=True,
            uncertainty_threshold=api.UNCERTAINTY_THRESHOLD,
        )


class FlagAwareAcceptedPredictor(FakePredictor):
    def __init__(self) -> None:
        self.received_flag: bool | None = None

    def predict(
        self,
        image: Image.Image,
        *,
        analyze_outside_domain: bool = False,
    ) -> api.PredictionResponse:
        self.received_flag = analyze_outside_domain
        return super().predict(image, analyze_outside_domain=False)


class FailingPredictor(FakePredictor):
    def predict(
        self,
        image: Image.Image,
        *,
        analyze_outside_domain: bool = False,
    ) -> api.PredictionResponse:
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
        "domain_guard_loaded": True,
        "domain_guard_sha256": "1" * 64,
        "domain_guard_method": "fake_cosine_guard",
        "domain_threshold": 0.65,
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
    assert payload["status"] == "classified"
    assert payload["is_supported_image"] is True
    assert payload["domain_score"] == 0.91
    assert payload["category_label"] == "Hoja sana"
    assert payload["score"] == 0.8
    assert payload["is_uncertain"] is False
    assert payload["uncertainty_threshold"] == 0.7
    assert [item["category"] for item in payload["scores"]] == api.EXPECTED_CLASS_ORDER
    assert sum(item["score"] for item in payload["scores"]) == pytest.approx(1.0)


def test_outside_domain_response_does_not_expose_a_coffee_class(client: TestClient) -> None:
    client.app.state.predictor = OutsideDomainPredictor()

    response = client.post(
        "/predict",
        files={"file": ("perro.jpg", image_bytes("JPEG"), "image/jpeg")},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "outside_domain"
    assert payload["is_supported_image"] is False
    assert payload["message"] == api.OUTSIDE_DOMAIN_MESSAGE
    assert payload["category"] is None
    assert payload["category_label"] is None
    assert payload["score"] is None
    assert payload["scores"] == []


def test_explicit_outside_domain_analysis_exposes_limited_comparison(client: TestClient) -> None:
    client.app.state.predictor = OutsideDomainPredictor()

    response = client.post(
        "/predict",
        data={"analyze_outside_domain": "true"},
        files={"file": ("hoja-externa.jpg", image_bytes("JPEG"), "image/jpeg")},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "outside_domain_analyzed"
    assert payload["is_supported_image"] is False
    assert payload["domain_score"] == 0.31
    assert payload["message"] == api.OUTSIDE_DOMAIN_ANALYZED_MESSAGE
    assert payload["category"] == "coffee___rust"
    assert payload["category_label"] == "Roya"
    assert payload["score"] == 0.6
    assert payload["is_uncertain"] is True
    assert [item["category"] for item in payload["scores"]] == api.EXPECTED_CLASS_ORDER
    assert sum(item["score"] for item in payload["scores"]) == pytest.approx(1.0)


def test_explicit_false_keeps_the_initial_domain_rejection(client: TestClient) -> None:
    client.app.state.predictor = OutsideDomainPredictor()

    response = client.post(
        "/predict",
        data={"analyze_outside_domain": "false"},
        files={"file": ("hoja-externa.jpg", image_bytes("JPEG"), "image/jpeg")},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "outside_domain"
    assert response.json()["scores"] == []


def test_override_flag_does_not_change_an_accepted_image(client: TestClient) -> None:
    predictor = FlagAwareAcceptedPredictor()
    client.app.state.predictor = predictor

    response = client.post(
        "/predict",
        data={"analyze_outside_domain": "true"},
        files={"file": ("hoja.jpg", image_bytes("JPEG"), "image/jpeg")},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "classified"
    assert response.json()["is_supported_image"] is True
    assert predictor.received_flag is True


def test_rejects_an_invalid_override_boolean(client: TestClient) -> None:
    response = client.post(
        "/predict",
        data={"analyze_outside_domain": "quizás"},
        files={"file": ("hoja.jpg", image_bytes("JPEG"), "image/jpeg")},
    )

    assert response.status_code == 422


def test_predictor_override_only_changes_result_exposure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    predictor = object.__new__(api.Predictor)
    predictor.model = object()
    predictor.classes = api.EXPECTED_CLASS_ORDER
    predictor.preprocess = lambda image: torch.zeros((3, 224, 224))
    predictor.domain_guard = type(
        "Guard",
        (),
        {
            "threshold": 0.65,
            "scores": staticmethod(lambda embedding: torch.tensor([0.31])),
        },
    )()
    logits = torch.tensor([[0.2, -0.4, 1.1]])
    embedding = torch.zeros((1, 576))
    monkeypatch.setattr(
        api,
        "mobilenet_logits_and_embedding",
        lambda model, tensor: (logits, embedding),
    )
    image = Image.new("RGB", (32, 24), (72, 112, 65))

    rejected = predictor.predict(image)
    analyzed = predictor.predict(image, analyze_outside_domain=True)

    assert rejected.status == "outside_domain"
    assert rejected.scores == []
    assert analyzed.status == "outside_domain_analyzed"
    assert analyzed.is_supported_image is False
    assert analyzed.domain_score == rejected.domain_score
    assert analyzed.category == "coffee___rust"
    assert [item.score for item in analyzed.scores] == pytest.approx(
        torch.softmax(logits, dim=1)[0].tolist()
    )


def valid_prediction_payload() -> dict[str, object]:
    return {
        "status": "classified",
        "is_supported_image": True,
        "domain_score": 0.91,
        "domain_threshold": 0.65,
        "message": None,
        "category": "coffee___healthy",
        "category_label": "Hoja sana",
        "score": 0.8,
        "scores": [
            {"category": "coffee___healthy", "label": "Hoja sana", "score": 0.8},
            {
                "category": "coffee___red_spider_mite",
                "label": "Ácaro rojo",
                "score": 0.1,
            },
            {"category": "coffee___rust", "label": "Roya", "score": 0.1},
        ],
        "is_uncertain": False,
        "uncertainty_threshold": api.UNCERTAINTY_THRESHOLD,
    }


@pytest.mark.parametrize(
    ("field", "invalid_value"),
    [
        ("category_label", "Roya"),
        ("score", 0.7),
        ("uncertainty_threshold", 0.5),
    ],
)
def test_prediction_response_rejects_incoherent_selected_result(
    field: str,
    invalid_value: object,
) -> None:
    payload = valid_prediction_payload()
    payload[field] = invalid_value

    with pytest.raises(ValueError):
        api.PredictionResponse(**payload)


def test_prediction_response_rejects_wrong_score_order_and_sum() -> None:
    wrong_order = valid_prediction_payload()
    wrong_order["scores"] = list(reversed(wrong_order["scores"]))
    with pytest.raises(ValueError):
        api.PredictionResponse(**wrong_order)

    wrong_sum = valid_prediction_payload()
    wrong_sum["scores"] = [
        {"category": "coffee___healthy", "label": "Hoja sana", "score": 0.8},
        {
            "category": "coffee___red_spider_mite",
            "label": "Ácaro rojo",
            "score": 0.15,
        },
        {"category": "coffee___rust", "label": "Roya", "score": 0.15},
    ]
    with pytest.raises(ValueError):
        api.PredictionResponse(**wrong_sum)


def test_outside_domain_response_must_remain_uncertain() -> None:
    with pytest.raises(ValueError):
        api.PredictionResponse(
            status="outside_domain",
            is_supported_image=False,
            domain_score=0.31,
            domain_threshold=0.65,
            message=api.OUTSIDE_DOMAIN_MESSAGE,
            is_uncertain=False,
            uncertainty_threshold=api.UNCERTAINTY_THRESHOLD,
        )


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
