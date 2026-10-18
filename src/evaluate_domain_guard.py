from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path

import torch
from PIL import Image, ImageOps

from src.common import ROOT, load_checkpoint, transform
from src.domain_guard import DomainGuard, extract_mobilenet_embedding


CRITERIA = {
    "coffee_overall_acceptance_min": 0.90,
    "coffee_each_class_acceptance_min": 0.80,
    "plantvillage_rejection_min": 0.90,
    "object_rejection_min": 0.95,
    "dog_rejection_min": 0.95,
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_external_embeddings(model, rows: list[dict[str, str]], batch_size: int) -> torch.Tensor:
    preprocessing = transform(training=False)
    batches: list[torch.Tensor] = []
    tensors: list[torch.Tensor] = []
    with torch.inference_mode():
        for row in rows:
            with Image.open(ROOT / row["path"]) as image:
                tensors.append(preprocessing(ImageOps.exif_transpose(image).convert("RGB")))
            if len(tensors) == batch_size:
                batches.append(extract_mobilenet_embedding(model, torch.stack(tensors)).cpu())
                tensors.clear()
        if tensors:
            batches.append(extract_mobilenet_embedding(model, torch.stack(tensors)).cpu())
    return torch.cat(batches)


def rate(values: list[bool]) -> float:
    if not values:
        raise ValueError("No hay ejemplos para calcular la tasa")
    return sum(values) / len(values)


def main() -> None:
    parser = argparse.ArgumentParser(description="Evalúa el filtro experimental sin usar TEST")
    parser.add_argument("--guard", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--benchmark-manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--batch-size", type=int, default=16)
    args = parser.parse_args()

    guard_path = args.guard if args.guard.is_absolute() else ROOT / args.guard
    checkpoint_path = args.checkpoint if args.checkpoint.is_absolute() else ROOT / args.checkpoint
    manifest_path = args.benchmark_manifest if args.benchmark_manifest.is_absolute() else ROOT / args.benchmark_manifest
    output_dir = args.output_dir if args.output_dir.is_absolute() else ROOT / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    if any(output_dir.iterdir()):
        raise FileExistsError(f"El directorio de resultados no está vacío: {output_dir}")

    guard = DomainGuard.load(guard_path)
    checkpoint_sha256 = sha256_file(checkpoint_path)
    if checkpoint_sha256 != guard.metadata.get("checkpoint_sha256"):
        raise RuntimeError("El filtro y el checkpoint no corresponden")
    model, checkpoint = load_checkpoint(checkpoint_path)
    if checkpoint.get("model") != "mobilenet":
        raise ValueError("El checkpoint no es MobileNet")

    with manifest_path.open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    embeddings = load_external_embeddings(model, rows, args.batch_size)
    scores = guard.scores(embeddings).tolist()
    accepted = [score >= guard.threshold for score in scores]

    grouped: dict[tuple[str, str], list[bool]] = defaultdict(list)
    for row, is_accepted in zip(rows, accepted, strict=True):
        grouped[(row["source"], row["detail"])].append(is_accepted)

    details = {
        f"{source}:{detail}": {
            "count": len(values),
            "accepted": sum(values),
            "rejected": len(values) - sum(values),
            "rejection_rate": 1.0 - rate(values),
        }
        for (source, detail), values in sorted(grouped.items())
    }
    plant_values = [value for row, value in zip(rows, accepted, strict=True) if row["source"] == "plantvillage"]
    object_values = [
        value
        for row, value in zip(rows, accepted, strict=True)
        if row["source"] in {"wikimedia_commons", "cifar10", "github_objects"}
    ]
    dog_values = [
        value
        for row, value in zip(rows, accepted, strict=True)
        if row["source"] in {"wikimedia_commons", "cifar10", "github_objects"} and row["detail"] == "dog"
    ]

    build_summary_path = guard_path.parent / "build_summary.json"
    build_summary = json.loads(build_summary_path.read_text(encoding="utf-8"))
    coffee_overall = float(build_summary["evaluation_acceptance"])
    coffee_per_class = {
        label: float(metrics["acceptance_rate"])
        for label, metrics in build_summary["evaluation_per_class"].items()
    }
    plant_rejection = 1.0 - rate(plant_values)
    object_rejection = 1.0 - rate(object_values) if object_values else None
    dog_rejection = 1.0 - rate(dog_values) if dog_values else None
    checks = {
        "coffee_overall": coffee_overall >= CRITERIA["coffee_overall_acceptance_min"],
        "coffee_each_class": all(
            value >= CRITERIA["coffee_each_class_acceptance_min"] for value in coffee_per_class.values()
        ),
        "plantvillage": plant_rejection >= CRITERIA["plantvillage_rejection_min"],
        "objects": object_rejection is not None and object_rejection >= CRITERIA["object_rejection_min"],
        "dogs": dog_rejection is not None and dog_rejection >= CRITERIA["dog_rejection_min"],
    }

    with (output_dir / "external_scores.csv").open("w", newline="", encoding="utf-8") as handle:
        fieldnames = list(rows[0]) + ["domain_score", "accepted_as_coffee_domain"]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row, score, is_accepted in zip(rows, scores, accepted, strict=True):
            writer.writerow({**row, "domain_score": score, "accepted_as_coffee_domain": is_accepted})

    benchmark_complete = bool(object_values and dog_values)
    status = (
        "passes_development_gate"
        if benchmark_complete and all(checks.values())
        else "fails_development_gate"
        if benchmark_complete
        else "partial_benchmark_not_integrated"
    )
    summary = {
        "status": status,
        "integrated": False,
        "test_used": False,
        "guard_sha256": sha256_file(guard_path),
        "checkpoint_sha256": checkpoint_sha256,
        "threshold": guard.threshold,
        "criteria": CRITERIA,
        "checks": checks,
        "coffee_evaluation_acceptance": coffee_overall,
        "coffee_evaluation_acceptance_by_class": coffee_per_class,
        "plantvillage_rejection": plant_rejection,
        "object_rejection": object_rejection,
        "dog_rejection": dog_rejection,
        "external_details": details,
        "limitations": [
            "La muestra de objetos no representa todas las cargas posibles.",
            "PlantVillage no representa todas las hojas o condiciones de campo.",
            "El score de similitud no es una probabilidad ni una garantía de pertenencia al café.",
        ],
    }
    (output_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
