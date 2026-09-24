"""Evalúa exclusivamente validación; no accede a la partición de prueba."""

import argparse
import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path

import torch
from sklearn.metrics import confusion_matrix, precision_recall_fscore_support
from torch.utils.data import DataLoader

from src.common import ROOT, Leaves, load_checkpoint, read_rows


DISPLAY_NAMES = {
    "coffee___healthy": "Hoja sana",
    "coffee___red_spider_mite": "Ácaro rojo",
    "coffee___rust": "Roya",
}
OUTPUT_NAMES = (
    "validation_metrics.json",
    "validation_predictions.csv",
    "validation_errors.csv",
    "validation_error_sample.csv",
    "validation_confusion_matrix.csv",
    "validation_report.md",
)


def _write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _markdown_table(headers: list[str], rows: list[list[str]]) -> str:
    header = "| " + " | ".join(headers) + " |"
    separator = "|" + "|".join("---" for _ in headers) + "|"
    body = ["| " + " | ".join(row) + " |" for row in rows]
    return "\n".join([header, separator, *body])


def main() -> None:
    parser = argparse.ArgumentParser(description="Métricas explícitas sobre validación, nunca sobre prueba.")
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--errors-per-pair", type=int, default=5)
    args = parser.parse_args()
    if args.batch_size < 1 or args.errors_per_pair < 1:
        parser.error("batch-size y errors-per-pair deben ser positivos")

    checkpoint_path = args.checkpoint if args.checkpoint.is_absolute() else ROOT / args.checkpoint
    output_dir = args.output_dir if args.output_dir.is_absolute() else ROOT / args.output_dir
    if not checkpoint_path.is_file():
        raise FileNotFoundError(f"No existe el checkpoint: {checkpoint_path}")
    output_dir.mkdir(parents=True, exist_ok=True)
    collisions = [name for name in OUTPUT_NAMES if (output_dir / name).exists()]
    if collisions:
        raise FileExistsError(f"No se sobrescribirán evidencias existentes: {collisions}")

    manifest_path = ROOT / "data/processed/manifest.csv"
    manifest_sha256 = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    model, checkpoint = load_checkpoint(checkpoint_path)
    if checkpoint["manifest_sha256"] != manifest_sha256:
        raise ValueError("El checkpoint no corresponde al manifiesto actual")

    declared_trainable = checkpoint.get("trainable_parameter_names")
    if declared_trainable is not None:
        parameters = dict(model.named_parameters())
        unknown = sorted(set(declared_trainable) - set(parameters))
        if unknown:
            raise ValueError(f"El checkpoint declara parámetros entrenables desconocidos: {unknown}")
        declared_trainable = set(declared_trainable)
        for name, parameter in parameters.items():
            parameter.requires_grad = name in declared_trainable

    classes = checkpoint["classes"]
    if set(classes) != set(DISPLAY_NAMES):
        raise ValueError(f"Clases inesperadas en el checkpoint: {classes}")
    rows = [row for row in read_rows() if row["split"] == "val"]
    if not rows:
        raise ValueError("El manifiesto no contiene imágenes de validación")

    loader = DataLoader(Leaves(rows, classes, training=False), batch_size=args.batch_size, shuffle=False)
    predictions: list[dict] = []
    truth: list[int] = []
    predicted: list[int] = []
    offset = 0
    with torch.inference_mode():
        for images, targets in loader:
            probabilities = torch.softmax(model(images), dim=1)
            batch_predictions = probabilities.argmax(dim=1)
            for index in range(len(targets)):
                row = rows[offset + index]
                true_index = int(targets[index])
                predicted_index = int(batch_predictions[index])
                scores = probabilities[index].tolist()
                record = {
                    "path": row["path"],
                    "group": row["group"],
                    "true_category": classes[true_index],
                    "true_label": DISPLAY_NAMES[classes[true_index]],
                    "predicted_category": classes[predicted_index],
                    "predicted_label": DISPLAY_NAMES[classes[predicted_index]],
                    "predicted_score": float(scores[predicted_index]),
                    "correct": true_index == predicted_index,
                }
                for class_index, category in enumerate(classes):
                    record[f"score_{category}"] = float(scores[class_index])
                predictions.append(record)
                truth.append(true_index)
                predicted.append(predicted_index)
            offset += len(targets)

    label_indexes = list(range(len(classes)))
    precision, recall, f1, support = precision_recall_fscore_support(
        truth,
        predicted,
        labels=label_indexes,
        zero_division=0,
    )
    matrix = confusion_matrix(truth, predicted, labels=label_indexes)
    macro_f1 = float(f1.mean())
    accuracy = float(sum(record["correct"] for record in predictions) / len(predictions))
    class_metrics = {
        category: {
            "label": DISPLAY_NAMES[category],
            "precision": float(precision[index]),
            "recall": float(recall[index]),
            "f1": float(f1[index]),
            "support": int(support[index]),
        }
        for index, category in enumerate(classes)
    }

    errors = [record for record in predictions if not record["correct"]]
    grouped_errors: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for record in errors:
        grouped_errors[(record["true_category"], record["predicted_category"])].append(record)
    error_sample: list[dict] = []
    for pair in sorted(grouped_errors):
        ranked = sorted(grouped_errors[pair], key=lambda record: (-record["predicted_score"], record["path"]))
        for record in ranked[: args.errors_per_pair]:
            error_sample.append({**record, "selection_reason": "mayor puntuación errónea dentro del par real/predicha"})

    trainable_names = [name for name, parameter in model.named_parameters() if parameter.requires_grad]
    trainable_count = sum(parameter.numel() for parameter in model.parameters() if parameter.requires_grad)
    total_count = sum(parameter.numel() for parameter in model.parameters())
    metrics = {
        "evaluation_split": "val",
        "sample_count": len(rows),
        "error_count": len(errors),
        "accuracy_descriptive_only": accuracy,
        "macro_f1_selection_metric": macro_f1,
        "class_order": classes,
        "display_labels": [DISPLAY_NAMES[category] for category in classes],
        "per_class": class_metrics,
        "confusion_matrix_rows_true_columns_predicted": matrix.tolist(),
        "checkpoint": {
            "path": str(checkpoint_path.relative_to(ROOT)) if checkpoint_path.is_relative_to(ROOT) else str(checkpoint_path),
            "model": checkpoint["model"],
            "seed": checkpoint["seed"],
            "epochs": checkpoint["epochs"],
            "selected_val_macro_f1": checkpoint["val_macro_f1"],
            "sha256": hashlib.sha256(checkpoint_path.read_bytes()).hexdigest(),
        },
        "manifest_sha256": manifest_sha256,
        "trainable_parameters": {
            "count": trainable_count,
            "total": total_count,
            "fraction": trainable_count / total_count,
            "names": trainable_names,
        },
        "preprocessing": {
            "orientation": "ImageOps.exif_transpose",
            "color": "RGB",
            "resize": [224, 224],
            "tensor": "ToTensor",
            "normalization_mean": [0.485, 0.456, 0.406],
            "normalization_std": [0.229, 0.224, 0.225],
            "validation_augmentation": False,
            "training_augmentation": ["RandomHorizontalFlip", "RandomRotation(15 grados)"],
        },
        "error_sample_policy": f"Hasta {args.errors_per_pair} errores por par real/predicha, ordenados por puntuación errónea descendente.",
    }

    common_fields = [
        "path",
        "group",
        "true_category",
        "true_label",
        "predicted_category",
        "predicted_label",
        "predicted_score",
        "correct",
        *[f"score_{category}" for category in classes],
    ]
    (output_dir / "validation_metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    _write_csv(output_dir / "validation_predictions.csv", predictions, common_fields)
    _write_csv(output_dir / "validation_errors.csv", errors, common_fields)
    _write_csv(
        output_dir / "validation_error_sample.csv",
        error_sample,
        [*common_fields, "selection_reason"],
    )

    matrix_rows = []
    for row_index, category in enumerate(classes):
        matrix_rows.append(
            {"real/predicha": DISPLAY_NAMES[category], **{
                DISPLAY_NAMES[predicted_category]: int(matrix[row_index, column_index])
                for column_index, predicted_category in enumerate(classes)
            }}
        )
    _write_csv(
        output_dir / "validation_confusion_matrix.csv",
        matrix_rows,
        ["real/predicha", *[DISPLAY_NAMES[category] for category in classes]],
    )

    metric_rows = [
        [
            DISPLAY_NAMES[category],
            f"{class_metrics[category]['precision']:.6f}",
            f"{class_metrics[category]['recall']:.6f}",
            f"{class_metrics[category]['f1']:.6f}",
            str(class_metrics[category]["support"]),
        ]
        for category in classes
    ]
    matrix_markdown_rows = [
        [DISPLAY_NAMES[category], *[str(int(value)) for value in matrix[index]]]
        for index, category in enumerate(classes)
    ]
    report = "\n".join(
        [
            f"# Validación: {checkpoint['model']}",
            "",
            "Evaluación exclusiva de la partición `val`. No se leyó ni evaluó `test`.",
            "",
            f"- Imágenes de validación: {len(rows)}",
            f"- F1 macro: {macro_f1:.10f}",
            f"- Errores: {len(errors)}",
            f"- Semilla del checkpoint: {checkpoint['seed']}",
            f"- SHA256 del manifiesto: `{manifest_sha256}`",
            "",
            "## Métricas por clase",
            "",
            _markdown_table(["Clase", "Precision", "Recall", "F1", "Soporte"], metric_rows),
            "",
            "## Matriz de confusión",
            "",
            "Filas: clase real. Columnas: clase predicha.",
            "",
            _markdown_table(
                ["Real / predicha", *[DISPLAY_NAMES[category] for category in classes]],
                matrix_markdown_rows,
            ),
            "",
            "## Parámetros entrenables del checkpoint cargado",
            "",
            f"{trainable_count} de {total_count} parámetros ({trainable_count / total_count:.2%}).",
            "",
            "Nombres: " + ", ".join(f"`{name}`" for name in trainable_names),
            "",
            "## Preprocesamiento",
            "",
            "EXIF transpose → RGB → Resize 224×224 → ToTensor → normalización ImageNet "
            "(media 0.485/0.456/0.406; desviación 0.229/0.224/0.225). "
            "Validación no usa aumento. Entrenamiento añade volteo horizontal aleatorio y rotación aleatoria de ±15°.",
            "",
            "## Evidencia para inspección",
            "",
            "`validation_predictions.csv` contiene todas las predicciones; `validation_errors.csv`, todos los errores; "
            "`validation_error_sample.csv`, hasta cinco errores con mayor puntuación por cada par real/predicha.",
            "",
        ]
    )
    (output_dir / "validation_report.md").write_text(report, encoding="utf-8")
    print(json.dumps(metrics, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
