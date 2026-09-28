"""Comprueba la inferencia web con una imagen de TRAIN, sin consultar TEST."""

from __future__ import annotations

import argparse
import csv
import hashlib
import http.client
import json
import uuid
from pathlib import Path
from urllib.parse import urlsplit

import torch
from PIL import Image, ImageOps

from src.common import ROOT, load_checkpoint, transform


EXPECTED_CLASSES = [
    "coffee___healthy",
    "coffee___red_spider_mite",
    "coffee___rust",
]
MAX_FILE_SIZE = 10 * 1024 * 1024


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def first_train_path() -> Path:
    with (ROOT / "data/processed/manifest.csv").open(encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row["split"] == "train":
                return ROOT / row["path"]
    raise RuntimeError("El manifiesto no contiene filas de TRAIN")


def connection(base_url: str) -> tuple[http.client.HTTPConnection, str]:
    parsed = urlsplit(base_url)
    if parsed.scheme != "http" or not parsed.hostname:
        raise ValueError("Este verificador local requiere una URL http:// válida")
    port = parsed.port or 80
    prefix = parsed.path.rstrip("/")
    return http.client.HTTPConnection(parsed.hostname, port, timeout=120), prefix


def get_json(base_url: str, endpoint: str) -> tuple[int, dict]:
    client, prefix = connection(base_url)
    try:
        client.request("GET", f"{prefix}{endpoint}")
        response = client.getresponse()
        payload = json.loads(response.read().decode("utf-8"))
        return response.status, payload
    finally:
        client.close()


def post_file(
    base_url: str,
    *,
    filename: str,
    content_type: str,
    data: bytes,
) -> tuple[int, dict]:
    boundary = f"cafeia-{uuid.uuid4().hex}"
    body = b"".join(
        [
            f"--{boundary}\r\n".encode(),
            f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'.encode(),
            f"Content-Type: {content_type}\r\n\r\n".encode(),
            data,
            f"\r\n--{boundary}--\r\n".encode(),
        ]
    )
    client, prefix = connection(base_url)
    try:
        client.request(
            "POST",
            f"{prefix}/predict",
            body=body,
            headers={
                "Content-Type": f"multipart/form-data; boundary={boundary}",
                "Content-Length": str(len(body)),
            },
        )
        response = client.getresponse()
        raw = response.read()
        payload = json.loads(raw.decode("utf-8")) if raw else {}
        return response.status, payload
    finally:
        client.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--checkpoint", type=Path, default=Path("models/mobilenet_finetuned_epoch6.pt"))
    parser.add_argument("--expected-sha256", required=True)
    args = parser.parse_args()

    checkpoint_path = args.checkpoint if args.checkpoint.is_absolute() else ROOT / args.checkpoint
    checkpoint_hash = sha256_file(checkpoint_path)
    if checkpoint_hash != args.expected_sha256.lower():
        raise RuntimeError(f"SHA256 inesperado: {checkpoint_hash}")

    model, checkpoint = load_checkpoint(checkpoint_path)
    if checkpoint["classes"] != EXPECTED_CLASSES:
        raise RuntimeError(f"Orden de clases inesperado: {checkpoint['classes']}")
    manifest_hash = sha256_file(ROOT / "data/processed/manifest.csv")
    if checkpoint["manifest_sha256"] != manifest_hash:
        raise RuntimeError("El checkpoint no corresponde al manifiesto actual")

    image_path = first_train_path()
    image_bytes = image_path.read_bytes()
    with Image.open(image_path) as image:
        rgb = ImageOps.exif_transpose(image).convert("RGB")
        tensor = transform(training=False)(rgb).unsqueeze(0)
    with torch.inference_mode():
        direct_scores = torch.softmax(model(tensor), dim=1)[0].tolist()

    health_status, health = get_json(args.base_url, "/health")
    prediction_status, prediction = post_file(
        args.base_url,
        filename=image_path.name,
        content_type="image/jpeg",
        data=image_bytes,
    )
    api_scores = {item["category"]: item["score"] for item in prediction.get("scores", [])}
    score_differences = {
        category: abs(float(direct_scores[index]) - float(api_scores.get(category, float("nan"))))
        for index, category in enumerate(EXPECTED_CLASSES)
    }
    max_score_difference = max(score_differences.values())

    invalid_status, invalid_payload = post_file(
        args.base_url,
        filename="contenido-invalido.jpg",
        content_type="image/jpeg",
        data=b"esto no es una imagen",
    )
    mismatch_status, mismatch_payload = post_file(
        args.base_url,
        filename="extension-falsa.png",
        content_type="image/png",
        data=image_bytes,
    )
    oversized_status, oversized_payload = post_file(
        args.base_url,
        filename="demasiado-grande.jpg",
        content_type="image/jpeg",
        data=b"x" * (MAX_FILE_SIZE + 1),
    )

    checks = {
        "health_http_200": health_status == 200,
        "health_checkpoint_sha256": health.get("checkpoint_sha256") == checkpoint_hash,
        "health_class_order": health.get("classes") == EXPECTED_CLASSES,
        "prediction_http_200": prediction_status == 200,
        "prediction_category_matches_direct": prediction.get("category")
        == EXPECTED_CLASSES[max(range(len(direct_scores)), key=direct_scores.__getitem__)],
        "all_scores_match_within_1e-7": max_score_difference <= 1e-7,
        "invalid_content_rejected_400": invalid_status == 400,
        "format_mismatch_rejected_415": mismatch_status == 415,
        "oversized_rejected_413": oversized_status == 413,
    }
    if not all(checks.values()):
        raise RuntimeError(f"Falló la verificación: {checks}")

    print(
        json.dumps(
            {
                "data_scope": "TRAIN only; TEST not read",
                "checkpoint_path": str(checkpoint_path.relative_to(ROOT)),
                "checkpoint_sha256": checkpoint_hash,
                "manifest_sha256": manifest_hash,
                "checkpoint_epoch": checkpoint.get("selected_candidate_epoch"),
                "class_order": EXPECTED_CLASSES,
                "preprocessing": {
                    "orientation": "ImageOps.exif_transpose",
                    "color": "RGB",
                    "resize": [224, 224],
                    "tensor": "ToTensor",
                    "normalization_mean": [0.485, 0.456, 0.406],
                    "normalization_std": [0.229, 0.224, 0.225],
                },
                "sample": str(image_path.relative_to(ROOT)),
                "direct_scores": dict(zip(EXPECTED_CLASSES, direct_scores, strict=True)),
                "api_scores": api_scores,
                "score_absolute_differences": score_differences,
                "max_score_absolute_difference": max_score_difference,
                "invalid_content_response": {"status": invalid_status, "payload": invalid_payload},
                "format_mismatch_response": {"status": mismatch_status, "payload": mismatch_payload},
                "oversized_response": {"status": oversized_status, "payload": oversized_payload},
                "checks": checks,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
