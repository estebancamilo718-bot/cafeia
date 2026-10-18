from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import torch
from torch.utils.data import DataLoader

from src.common import ROOT, Leaves, load_checkpoint, read_rows
from src.domain_guard import DomainGuard, extract_mobilenet_embedding


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def split_validation_groups(rows: list[dict[str, str]], seed: int) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    groups = sorted({row["group"] for row in rows})
    ranked = sorted(
        groups,
        key=lambda group: hashlib.sha256(f"{seed}:{group}".encode()).hexdigest(),
    )
    calibration_groups = set(ranked[::2])
    calibration = [row for row in rows if row["group"] in calibration_groups]
    evaluation = [row for row in rows if row["group"] not in calibration_groups]
    if not calibration or not evaluation:
        raise RuntimeError("No fue posible separar VAL por grupos")
    if {row["group"] for row in calibration} & {row["group"] for row in evaluation}:
        raise RuntimeError("Hay grupos compartidos entre calibración y evaluación")
    return calibration, evaluation


def embeddings_for_rows(model, rows, classes, batch_size: int) -> torch.Tensor:
    loader = DataLoader(
        Leaves(rows, classes, training=False),
        batch_size=batch_size,
        shuffle=False,
        num_workers=0,
    )
    chunks: list[torch.Tensor] = []
    with torch.inference_mode():
        for images, _ in loader:
            chunks.append(extract_mobilenet_embedding(model, images).cpu())
    return torch.cat(chunks)


def counts(rows: list[dict[str, str]]) -> dict[str, int]:
    return dict(sorted(Counter(row["label"] for row in rows).items()))


def main() -> None:
    parser = argparse.ArgumentParser(description="Construye un filtro experimental sin consultar TEST")
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--neighbors", type=int, default=5)
    parser.add_argument("--target-acceptance", type=float, default=0.95)
    parser.add_argument("--batch-size", type=int, default=16)
    args = parser.parse_args()

    checkpoint_path = args.checkpoint if args.checkpoint.is_absolute() else ROOT / args.checkpoint
    actual_sha256 = sha256_file(checkpoint_path)
    if actual_sha256 != args.expected_sha256.lower():
        raise RuntimeError(f"SHA256 inesperado: {actual_sha256}")
    if not 0.5 < args.target_acceptance < 1.0:
        raise ValueError("target-acceptance debe estar entre 0.5 y 1")

    output_dir = args.output_dir
    if output_dir is None:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        output_dir = ROOT / "experiments" / f"domain_guard_{timestamp}"
    elif not output_dir.is_absolute():
        output_dir = ROOT / output_dir
    if output_dir.exists():
        raise FileExistsError(f"El directorio ya existe: {output_dir}")
    output_dir.mkdir(parents=True)

    rows = read_rows()
    if any(row["split"] == "test" for row in rows) is False:
        raise RuntimeError("El manifiesto no contiene la partición TEST reservada")
    train_rows = [row for row in rows if row["split"] == "train"]
    val_rows = [row for row in rows if row["split"] == "val"]
    calibration_rows, evaluation_rows = split_validation_groups(val_rows, args.seed)

    model, checkpoint = load_checkpoint(checkpoint_path)
    classes = list(checkpoint["classes"])
    if checkpoint.get("model") != "mobilenet":
        raise ValueError("El checkpoint no es MobileNet")

    reference_embeddings = embeddings_for_rows(model, train_rows, classes, args.batch_size)
    calibration_embeddings = embeddings_for_rows(model, calibration_rows, classes, args.batch_size)
    evaluation_embeddings = embeddings_for_rows(model, evaluation_rows, classes, args.batch_size)

    provisional = DomainGuard(reference_embeddings, 0.0, args.neighbors, {})
    calibration_scores = provisional.scores(calibration_embeddings)
    quantile = 1.0 - args.target_acceptance
    threshold = float(torch.quantile(calibration_scores, quantile, interpolation="lower"))

    manifest_path = ROOT / "data" / "processed" / "manifest.csv"
    metadata = {
        "method": "mean_top_k_cosine_penultimate_mobilenet_v3_small",
        "checkpoint": str(checkpoint_path.relative_to(ROOT)),
        "checkpoint_sha256": actual_sha256,
        "manifest_sha256": sha256_file(manifest_path),
        "classes": classes,
        "seed": args.seed,
        "neighbors": args.neighbors,
        "target_calibration_acceptance": args.target_acceptance,
        "threshold_source": "group_disjoint_half_of_val",
        "test_used": False,
        "reference_count": len(train_rows),
        "calibration_count": len(calibration_rows),
        "evaluation_count": len(evaluation_rows),
    }
    guard = DomainGuard(reference_embeddings, threshold, args.neighbors, metadata)
    artifact_path = output_dir / "domain_guard.pt"
    guard.save(artifact_path)

    evaluation_scores = guard.scores(evaluation_embeddings)
    evaluation_accepts = evaluation_scores >= threshold
    per_class: dict[str, dict[str, float | int]] = {}
    by_label: dict[str, list[int]] = defaultdict(list)
    for index, row in enumerate(evaluation_rows):
        by_label[row["label"]].append(index)
    for label, indices in sorted(by_label.items()):
        accepted = int(evaluation_accepts[indices].sum())
        per_class[label] = {
            "count": len(indices),
            "accepted": accepted,
            "acceptance_rate": accepted / len(indices),
        }

    with (output_dir / "validation_scores.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["partition", "path", "label", "group", "domain_score", "accepted"],
        )
        writer.writeheader()
        for partition, subset, scores in (
            ("calibration", calibration_rows, calibration_scores),
            ("evaluation", evaluation_rows, evaluation_scores),
        ):
            for row, score in zip(subset, scores.tolist(), strict=True):
                writer.writerow(
                    {
                        "partition": partition,
                        "path": row["path"],
                        "label": row["label"],
                        "group": row["group"],
                        "domain_score": score,
                        "accepted": score >= threshold,
                    }
                )

    summary = {
        "status": "built_not_integrated",
        "artifact": str(artifact_path.relative_to(ROOT)),
        "artifact_sha256": sha256_file(artifact_path),
        "threshold": threshold,
        "calibration_acceptance": float((calibration_scores >= threshold).float().mean()),
        "evaluation_acceptance": float(evaluation_accepts.float().mean()),
        "evaluation_per_class": per_class,
        "row_counts": {
            "train": counts(train_rows),
            "calibration": counts(calibration_rows),
            "evaluation": counts(evaluation_rows),
        },
        "metadata": metadata,
    }
    (output_dir / "build_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
