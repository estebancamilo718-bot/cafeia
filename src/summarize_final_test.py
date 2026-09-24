"""Consolida evidencias ya calculadas de la evaluación final.

No abre imágenes, no ejecuta modelos y no selecciona un checkpoint nuevo.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


CLASS_ORDER = [
    "coffee___healthy",
    "coffee___red_spider_mite",
    "coffee___rust",
]
MODELS = [
    {
        "id": "mobilenet_finetuned_epoch6",
        "role": "principal",
        "validation": "experiments/mobilenet_finetune_20260922-103426/validation_metrics.json",
    },
    {
        "id": "mobilenet_frozen_epoch9",
        "role": "reference",
        "validation": "experiments/mobilenet_10ep_20260920-181113/validation_metrics.json",
    },
    {
        "id": "resnet18_frozen_epoch8",
        "role": "reference",
        "validation": "experiments/resnet18_10ep_20260921-130620/validation_metrics.json",
    },
    {
        "id": "cnn_scratch_epoch7",
        "role": "reference",
        "validation": "experiments/cnn_10ep_20260921-125200/validation_metrics.json",
    },
]
OUTPUT_NAMES = ("model_comparison.csv", "validation_vs_test.csv", "final_summary.json")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--results-dir", type=Path, required=True)
    args = parser.parse_args()

    root = args.project_root.resolve()
    results_dir = args.results_dir if args.results_dir.is_absolute() else root / args.results_dir
    results_dir = results_dir.resolve()
    collisions = [name for name in OUTPUT_NAMES if (results_dir / name).exists()]
    if collisions:
        raise FileExistsError(f"No se sobrescribirán resúmenes existentes: {collisions}")

    protocol = read_json(results_dir / "protocol_snapshot.json")
    protocol_checkpoints = {item["id"]: item for item in protocol["checkpoints"]}
    comparison_rows: list[dict[str, Any]] = []
    validation_vs_test_rows: list[dict[str, Any]] = []
    summaries: dict[str, Any] = {}
    canonical_predictions: list[tuple[str, str, str]] | None = None

    for specification in MODELS:
        model_id = specification["id"]
        validation = read_json(root / specification["validation"])
        test_dir = results_dir / model_id
        test = read_json(test_dir / "test_metrics.json")
        predictions = read_csv(test_dir / "test_predictions.csv")

        if test["sample_count"] != protocol["test_sample_count"] or len(predictions) != test["sample_count"]:
            raise ValueError(f"Cantidad inesperada para {model_id}")
        if test["class_order"] != protocol["class_order"] or test["class_order"] != CLASS_ORDER:
            raise ValueError(f"Orden de clases incompatible para {model_id}")
        if test["manifest_sha256"] != protocol["manifest_sha256"]:
            raise ValueError(f"Manifiesto incompatible para {model_id}")
        if test["checkpoint"]["sha256"] != protocol_checkpoints[model_id]["sha256"]:
            raise ValueError(f"Checkpoint distinto al protocolo para {model_id}")

        identity = [(row["path"], row["sha256"], row["true_category"]) for row in predictions]
        if canonical_predictions is None:
            canonical_predictions = identity
        elif identity != canonical_predictions:
            raise ValueError(f"Las filas de TEST no coinciden para {model_id}")

        validation_f1 = float(validation["macro_f1_selection_metric"])
        validation_accuracy = float(validation["accuracy_descriptive_only"])
        comparison_row: dict[str, Any] = {
            "model_id": model_id,
            "role": specification["role"],
            "validation_macro_f1": validation_f1,
            "test_macro_f1": test["macro_f1"],
            "test_minus_validation_macro_f1": test["macro_f1"] - validation_f1,
            "validation_accuracy": validation_accuracy,
            "test_accuracy": test["accuracy"],
            "test_minus_validation_accuracy": test["accuracy"] - validation_accuracy,
            "test_macro_precision": test["macro_precision"],
            "test_macro_recall": test["macro_recall"],
            "test_error_count": test["error_count"],
        }
        for category in CLASS_ORDER:
            comparison_row[f"test_precision_{category}"] = test["per_class"][category]["precision"]
            comparison_row[f"test_recall_{category}"] = test["per_class"][category]["recall"]
            comparison_row[f"test_f1_{category}"] = test["per_class"][category]["f1"]
        comparison_rows.append(comparison_row)

        validation_vs_test_rows.extend(
            [
                {
                    "model_id": model_id,
                    "role": specification["role"],
                    "scope": "overall",
                    "class": "all",
                    "metric": "macro_f1",
                    "validation": validation_f1,
                    "test": test["macro_f1"],
                    "test_minus_validation": test["macro_f1"] - validation_f1,
                },
                {
                    "model_id": model_id,
                    "role": specification["role"],
                    "scope": "overall",
                    "class": "all",
                    "metric": "accuracy",
                    "validation": validation_accuracy,
                    "test": test["accuracy"],
                    "test_minus_validation": test["accuracy"] - validation_accuracy,
                },
            ]
        )
        for category in CLASS_ORDER:
            for metric in ("precision", "recall", "f1"):
                val_value = float(validation["per_class"][category][metric])
                test_value = float(test["per_class"][category][metric])
                validation_vs_test_rows.append(
                    {
                        "model_id": model_id,
                        "role": specification["role"],
                        "scope": "per_class",
                        "class": category,
                        "metric": metric,
                        "validation": val_value,
                        "test": test_value,
                        "test_minus_validation": test_value - val_value,
                    }
                )
        summaries[model_id] = {
            "role": specification["role"],
            "validation_metrics_path": specification["validation"],
            "test_metrics_path": str((test_dir / "test_metrics.json").relative_to(root)).replace("\\", "/"),
            "validation": validation,
            "test": test,
        }

    comparison_fields = list(comparison_rows[0])
    write_csv(results_dir / "model_comparison.csv", comparison_rows, comparison_fields)
    write_csv(
        results_dir / "validation_vs_test.csv",
        validation_vs_test_rows,
        ["model_id", "role", "scope", "class", "metric", "validation", "test", "test_minus_validation"],
    )
    final_summary = {
        "status": "complete",
        "selection_remained_fixed": True,
        "principal_candidate": protocol["principal_candidate"],
        "test_sample_count": protocol["test_sample_count"],
        "same_test_rows_and_order_for_all_models": True,
        "manifest_sha256": protocol["manifest_sha256"],
        "provisional_uncertainty_threshold": protocol["provisional_uncertainty_threshold"],
        "models": summaries,
    }
    (results_dir / "final_summary.json").write_text(
        json.dumps(final_summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps({"comparison": comparison_rows}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
