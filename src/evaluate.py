"""Evaluación final de un checkpoint explícito sobre la partición TEST.

Este módulo no selecciona modelos, no entrena y nunca escribe en ``models/``.
La selección debe haberse cerrado antes de ejecutarlo.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import time
from pathlib import Path

import torch
from sklearn.metrics import confusion_matrix, precision_recall_fscore_support
from torch.utils.data import DataLoader

from src.common import ROOT, Leaves, load_checkpoint, read_rows


CLASS_ORDER = [
    "coffee___healthy",
    "coffee___red_spider_mite",
    "coffee___rust",
]
DISPLAY_NAMES = {
    "coffee___healthy": "Hoja sana",
    "coffee___red_spider_mite": "Ácaro rojo",
    "coffee___rust": "Roya",
}
OUTPUT_NAMES = (
    "test_metrics.json",
    "test_predictions.csv",
    "test_errors.csv",
    "test_confusion_matrix.csv",
    "test_report.md",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def markdown_table(headers: list[str], rows: list[list[str]]) -> str:
    header = "| " + " | ".join(headers) + " |"
    separator = "|" + "|".join("---" for _ in headers) + "|"
    body = ["| " + " | ".join(row) + " |" for row in rows]
    return "\n".join([header, separator, *body])


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evalúa un checkpoint explícito sobre TEST sin modificar el modelo activo."
    )
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--model-label", required=True)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--expected-samples", type=int, default=300)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    parser.add_argument("--uncertainty-threshold", type=float)
    args = parser.parse_args()

    if args.batch_size < 1 or args.expected_samples < 1:
        parser.error("batch-size y expected-samples deben ser positivos")
    if args.uncertainty_threshold is not None and not 0.0 <= args.uncertainty_threshold <= 1.0:
        parser.error("uncertainty-threshold debe estar entre 0 y 1")
    if args.device == "cuda" and not torch.cuda.is_available():
        parser.error("CUDA no está disponible")

    checkpoint_path = args.checkpoint if args.checkpoint.is_absolute() else ROOT / args.checkpoint
    output_dir = args.output_dir if args.output_dir.is_absolute() else ROOT / args.output_dir
    checkpoint_path = checkpoint_path.resolve()
    output_dir = output_dir.resolve()
    models_dir = (ROOT / "models").resolve()
    if not checkpoint_path.is_file():
        raise FileNotFoundError(f"No existe el checkpoint: {checkpoint_path}")
    if output_dir == models_dir or models_dir in output_dir.parents:
        raise ValueError("El directorio de salida no puede estar dentro de models/")

    output_dir.mkdir(parents=True, exist_ok=True)
    collisions = [name for name in OUTPUT_NAMES if (output_dir / name).exists()]
    if collisions:
        raise FileExistsError(f"No se sobrescribirán evidencias existentes: {collisions}")

    manifest_path = ROOT / "data" / "processed" / "manifest.csv"
    manifest_sha256 = sha256_file(manifest_path)
    checkpoint_sha256 = sha256_file(checkpoint_path)
    model, checkpoint = load_checkpoint(checkpoint_path)
    if checkpoint.get("manifest_sha256") != manifest_sha256:
        raise ValueError("El checkpoint no corresponde al manifiesto fijado")
    if checkpoint.get("classes") != CLASS_ORDER:
        raise ValueError(
            f"Orden de clases incompatible: {checkpoint.get('classes')}; esperado: {CLASS_ORDER}"
        )
    if checkpoint.get("model") not in {"cnn", "mobilenet", "resnet18"}:
        raise ValueError(f"Arquitectura no admitida: {checkpoint.get('model')}")

    rows = [row for row in read_rows() if row["split"] == "test"]
    if len(rows) != args.expected_samples:
        raise ValueError(
            f"TEST contiene {len(rows)} imágenes; el protocolo exige {args.expected_samples}"
        )

    model = model.to(args.device)
    model.eval()
    loader = DataLoader(
        Leaves(rows, CLASS_ORDER, training=False),
        batch_size=args.batch_size,
        shuffle=False,
        num_workers=0,
    )

    predictions: list[dict] = []
    truth: list[int] = []
    predicted: list[int] = []
    offset = 0
    started = time.perf_counter()
    with torch.inference_mode():
        for images, targets in loader:
            scores_batch = torch.softmax(model(images.to(args.device)), dim=1).cpu()
            predictions_batch = scores_batch.argmax(dim=1)
            for index in range(len(targets)):
                row = rows[offset + index]
                true_index = int(targets[index])
                predicted_index = int(predictions_batch[index])
                scores = scores_batch[index].tolist()
                predicted_score = float(scores[predicted_index])
                record = {
                    "manifest_test_index": offset + index,
                    "path": row["path"],
                    "group": row["group"],
                    "sha256": row["sha256"],
                    "true_category": CLASS_ORDER[true_index],
                    "true_label": DISPLAY_NAMES[CLASS_ORDER[true_index]],
                    "predicted_category": CLASS_ORDER[predicted_index],
                    "predicted_label": DISPLAY_NAMES[CLASS_ORDER[predicted_index]],
                    "predicted_score": predicted_score,
                    "correct": true_index == predicted_index,
                }
                if args.uncertainty_threshold is not None:
                    record["meets_provisional_threshold"] = (
                        predicted_score >= args.uncertainty_threshold
                    )
                for class_index, category in enumerate(CLASS_ORDER):
                    record[f"score_{category}"] = float(scores[class_index])
                predictions.append(record)
                truth.append(true_index)
                predicted.append(predicted_index)
            offset += len(targets)
    duration_seconds = time.perf_counter() - started

    label_indexes = list(range(len(CLASS_ORDER)))
    precision, recall, f1, support = precision_recall_fscore_support(
        truth,
        predicted,
        labels=label_indexes,
        zero_division=0,
    )
    matrix = confusion_matrix(truth, predicted, labels=label_indexes)
    error_count = sum(not record["correct"] for record in predictions)
    accuracy = float((len(predictions) - error_count) / len(predictions))
    macro_precision = float(precision.mean())
    macro_recall = float(recall.mean())
    macro_f1 = float(f1.mean())
    class_metrics = {
        category: {
            "label": DISPLAY_NAMES[category],
            "precision": float(precision[index]),
            "recall": float(recall[index]),
            "f1": float(f1[index]),
            "support": int(support[index]),
        }
        for index, category in enumerate(CLASS_ORDER)
    }

    threshold_analysis = None
    if args.uncertainty_threshold is not None:
        accepted = [
            record
            for record in predictions
            if record["predicted_score"] >= args.uncertainty_threshold
        ]
        accepted_correct = sum(record["correct"] for record in accepted)
        threshold_analysis = {
            "threshold": args.uncertainty_threshold,
            "below_threshold_count": len(predictions) - len(accepted),
            "accepted_count": len(accepted),
            "accepted_proportion": len(accepted) / len(predictions),
            "accepted_correct_count": accepted_correct,
            "accepted_accuracy": accepted_correct / len(accepted) if accepted else None,
            "warning": (
                "Umbral provisional sobre puntuación softmax no calibrada; no detecta imágenes "
                "ajenas al café ni equivale a seguridad clínica o agronómica."
            ),
        }

    checkpoint_relative = (
        str(checkpoint_path.relative_to(ROOT)).replace("\\", "/")
        if checkpoint_path.is_relative_to(ROOT)
        else str(checkpoint_path)
    )
    metrics = {
        "evaluation_split": "test",
        "sample_count": len(predictions),
        "error_count": error_count,
        "accuracy": accuracy,
        "macro_precision": macro_precision,
        "macro_recall": macro_recall,
        "macro_f1": macro_f1,
        "class_order": CLASS_ORDER,
        "display_labels": [DISPLAY_NAMES[category] for category in CLASS_ORDER],
        "per_class": class_metrics,
        "confusion_matrix_rows_true_columns_predicted": matrix.tolist(),
        "checkpoint": {
            "path": checkpoint_relative,
            "sha256": checkpoint_sha256,
            "model_label": args.model_label,
            "architecture": checkpoint["model"],
            "seed": checkpoint["seed"],
            "epochs_recorded": checkpoint["epochs"],
            "selected_candidate_epoch": checkpoint.get("selected_candidate_epoch"),
            "selected_validation_macro_f1": checkpoint["val_macro_f1"],
        },
        "manifest_sha256": manifest_sha256,
        "preprocessing": {
            "implementation": "src.common.Leaves(..., training=False) / transform(False)",
            "orientation": "ImageOps.exif_transpose",
            "color": "RGB",
            "resize": [224, 224],
            "tensor": "ToTensor",
            "normalization_mean": [0.485, 0.456, 0.406],
            "normalization_std": [0.229, 0.224, 0.225],
            "test_augmentation": False,
        },
        "loader": {
            "batch_size": args.batch_size,
            "shuffle": False,
            "num_workers": 0,
            "device": args.device,
        },
        "duration_seconds": duration_seconds,
        "threshold_analysis": threshold_analysis,
    }

    fields = [
        "manifest_test_index",
        "path",
        "group",
        "sha256",
        "true_category",
        "true_label",
        "predicted_category",
        "predicted_label",
        "predicted_score",
        "correct",
    ]
    if args.uncertainty_threshold is not None:
        fields.append("meets_provisional_threshold")
    fields.extend(f"score_{category}" for category in CLASS_ORDER)

    (output_dir / "test_metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    write_csv(output_dir / "test_predictions.csv", predictions, fields)
    write_csv(
        output_dir / "test_errors.csv",
        [record for record in predictions if not record["correct"]],
        fields,
    )
    matrix_rows = [
        {
            "real/predicha": DISPLAY_NAMES[category],
            **{
                DISPLAY_NAMES[predicted_category]: int(matrix[row_index, column_index])
                for column_index, predicted_category in enumerate(CLASS_ORDER)
            },
        }
        for row_index, category in enumerate(CLASS_ORDER)
    ]
    write_csv(
        output_dir / "test_confusion_matrix.csv",
        matrix_rows,
        ["real/predicha", *[DISPLAY_NAMES[category] for category in CLASS_ORDER]],
    )

    metric_rows = [
        [
            DISPLAY_NAMES[category],
            f"{class_metrics[category]['precision']:.6f}",
            f"{class_metrics[category]['recall']:.6f}",
            f"{class_metrics[category]['f1']:.6f}",
            str(class_metrics[category]["support"]),
        ]
        for category in CLASS_ORDER
    ]
    matrix_markdown_rows = [
        [DISPLAY_NAMES[category], *[str(int(value)) for value in matrix[index]]]
        for index, category in enumerate(CLASS_ORDER)
    ]
    threshold_lines: list[str] = []
    if threshold_analysis is not None:
        threshold_lines = [
            "",
            "## Umbral provisional",
            "",
            f"- Umbral: {threshold_analysis['threshold']:.2f}",
            f"- Debajo del umbral: {threshold_analysis['below_threshold_count']}",
            f"- Aceptadas: {threshold_analysis['accepted_count']} "
            f"({threshold_analysis['accepted_proportion']:.2%})",
            f"- Correctas entre aceptadas: {threshold_analysis['accepted_correct_count']}",
            f"- Accuracy entre aceptadas: {threshold_analysis['accepted_accuracy']:.6f}"
            if threshold_analysis["accepted_accuracy"] is not None
            else "- Accuracy entre aceptadas: no definida (0 aceptadas)",
            "",
            threshold_analysis["warning"],
        ]
    report = "\n".join(
        [
            f"# TEST final: {args.model_label}",
            "",
            f"- Imágenes: {len(predictions)}",
            f"- F1 macro: {macro_f1:.10f}",
            f"- Accuracy: {accuracy:.10f}",
            f"- Errores: {error_count}",
            f"- Checkpoint: `{checkpoint_relative}`",
            f"- SHA-256: `{checkpoint_sha256}`",
            "",
            "## Métricas por clase",
            "",
            markdown_table(["Clase", "Precision", "Recall", "F1", "Soporte"], metric_rows),
            "",
            "## Matriz de confusión",
            "",
            "Filas: clase real. Columnas: clase predicha.",
            "",
            markdown_table(
                ["Real / predicha", *[DISPLAY_NAMES[category] for category in CLASS_ORDER]],
                matrix_markdown_rows,
            ),
            *threshold_lines,
            "",
            "Las puntuaciones guardadas son salidas softmax no calibradas y no constituyen un diagnóstico definitivo.",
            "",
        ]
    )
    (output_dir / "test_report.md").write_text(report, encoding="utf-8")
    print(json.dumps(metrics, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
