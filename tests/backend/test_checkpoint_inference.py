from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

import backend.main as api


CHECKPOINT = Path("models/mobilenet_finetuned_epoch6.pt")
CHECKPOINT_SHA256 = "4ab4e52fc3d417fe5fb126ff1e5b346f080c55ffa80232cffd5d6e6622e46c94"
MODEL_ID = "mobilenet-v3-small-finetuned-epoch6"
DOMAIN_GUARD = Path("models/coffee_domain_guard.pt")
DOMAIN_GUARD_SHA256 = "8060ef83e4a018d6a49e22fc5b59162f4ec6cbba90482e27d7896c79106d90e7"


def synthetic_jpeg() -> bytes:
    output = BytesIO()
    Image.new("RGB", (320, 240), (79, 118, 66)).save(output, format="JPEG", quality=90)
    return output.getvalue()


@pytest.mark.integration
def test_real_checkpoint_load_and_inference(monkeypatch: pytest.MonkeyPatch) -> None:
    """Carga pesos reales; no mide exactitud ni consulta TRAIN, VAL o TEST."""

    monkeypatch.setenv("MODEL_PATH", str(CHECKPOINT))
    monkeypatch.setenv("MODEL_SHA256", CHECKPOINT_SHA256)
    monkeypatch.setenv("MODEL_ID", MODEL_ID)
    monkeypatch.setenv("DOMAIN_GUARD_PATH", str(DOMAIN_GUARD))
    monkeypatch.setenv("DOMAIN_GUARD_SHA256", DOMAIN_GUARD_SHA256)

    with TestClient(api.app) as client:
        health = client.get("/health")
        prediction = client.post(
            "/predict",
            files={"file": ("sintetica.jpg", synthetic_jpeg(), "image/jpeg")},
        )

    assert health.status_code == 200
    health_payload = health.json()
    assert health_payload["model_id"] == MODEL_ID
    assert health_payload["checkpoint_sha256"] == CHECKPOINT_SHA256
    assert health_payload["domain_guard_loaded"] is True
    assert health_payload["domain_guard_sha256"] == DOMAIN_GUARD_SHA256
    assert health_payload["classes"] == api.EXPECTED_CLASS_ORDER

    assert prediction.status_code == 200
    payload = prediction.json()
    assert payload["status"] in {"classified", "uncertain", "outside_domain"}
    assert isinstance(payload["domain_score"], float)
    if payload["status"] == "outside_domain":
        assert payload["is_supported_image"] is False
        assert payload["category"] is None
        assert payload["scores"] == []
    else:
        assert payload["is_supported_image"] is True
        assert payload["category"] in api.EXPECTED_CLASS_ORDER
        assert [item["category"] for item in payload["scores"]] == api.EXPECTED_CLASS_ORDER
        assert sum(item["score"] for item in payload["scores"]) == pytest.approx(1.0, abs=1e-6)
        assert payload["is_uncertain"] == (payload["score"] < api.UNCERTAINTY_THRESHOLD)
