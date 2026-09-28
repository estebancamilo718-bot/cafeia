"""Experimento pareado de preprocesamiento para CaféIA v2.

La etapa ``preflight`` no entrena: verifica integridad, genera la lámina y
demuestra la equivalencia de la rama control reutilizada. La etapa ``train``
ejecuta únicamente el candidato sobre TRAIN/VAL y nunca abre imágenes TEST.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import shutil
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import numpy as np
import PIL
import torch
import torchvision
from PIL import Image, ImageDraw, ImageFont, ImageOps
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, precision_recall_fscore_support
from torch import nn
from torch.utils.data import DataLoader, Dataset

from src.common import ROOT, load_checkpoint, read_rows, transform as legacy_transform
from src.v2_preprocessing import (
    AspectPadToSquare,
    IMAGENET_MEAN,
    IMAGENET_STD,
    PADDING_RGB,
    build_transform,
    geometry_transform,
    preprocessing_config,
)


SEED = 42
BATCH_SIZE = 16
MAX_EPOCHS = 15
PATIENCE = 4
FEATURE_LEARNING_RATE = 1e-5
CLASSIFIER_LEARNING_RATE = 1e-4
EXPECTED_SOURCE_SHA256 = "9248cc767425c9efec643bcc2cabd758e8f2b28ab4a6967908713fc1d0b9c5c1"
EXPECTED_ACTIVE_SHA256 = "4ab4e52fc3d417fe5fb126ff1e5b346f080c55ffa80232cffd5d6e6622e46c94"
EXPECTED_MANIFEST_SHA256 = "1ea21d6b2b480b830065c5d4d1d90f531234cc2aa244d7bb98c5873363866dab"
SOURCE_CHECKPOINT = ROOT / "models" / "mobilenet.pt"
ACTIVE_CHECKPOINT = ROOT / "models" / "mobilenet_finetuned_epoch6.pt"
MANIFEST_PATH = ROOT / "data" / "processed" / "manifest.csv"
CONTROL_SOURCE_DIR = ROOT / "experiments" / "mobilenet_finetune_20260922-103426"
DISPLAY_NAMES = {
    "coffee___healthy": "Hoja sana",
    "coffee___red_spider_mite": "Ácaro rojo",
    "coffee___rust": "Roya",
}
VISUAL_EXAMPLES = (
    "data/raw/coffee___healthy/C10P12H1.jpg",
    "data/raw/coffee___red_spider_mite/C11P9H2.jpg",
    "data/raw/coffee___rust/C10P27E2.jpg",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def relative(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def integrity_snapshot() -> dict[str, dict[str, str]]:
    return {
        "source_checkpoint": {"path": relative(SOURCE_CHECKPOINT), "sha256": sha256(SOURCE_CHECKPOINT)},
        "active_web_checkpoint": {"path": relative(ACTIVE_CHECKPOINT), "sha256": sha256(ACTIVE_CHECKPOINT)},
        "manifest": {"path": relative(MANIFEST_PATH), "sha256": sha256(MANIFEST_PATH)},
    }


def require_expected_integrity(snapshot: dict[str, dict[str, str]]) -> None:
    expected = {
        "source_checkpoint": EXPECTED_SOURCE_SHA256,
        "active_web_checkpoint": EXPECTED_ACTIVE_SHA256,
        "manifest": EXPECTED_MANIFEST_SHA256,
    }
    mismatches = {
        name: {"expected": value, "actual": snapshot[name]["sha256"]}
        for name, value in expected.items()
        if snapshot[name]["sha256"] != value
    }
    if mismatches:
        raise RuntimeError(f"Falló la verificación de integridad: {mismatches}")


def new_experiment_dir() -> Path:
    base = ROOT / "experiments" / f"mobilenet_v2_preprocessing_{datetime.now():%Y%m%d-%H%M%S}"
    candidate = base
    suffix = 1
    while candidate.exists():
        candidate = Path(f"{base}-{suffix}")
        suffix += 1
    candidate.mkdir(parents=True)
    (candidate / "control").mkdir()
    (candidate / "candidate").mkdir()
    return candidate


class BranchLeaves(Dataset):
    def __init__(self, rows: list[dict[str, str]], classes: list[str], variant: str, training: bool):
        self.rows = rows
        self.classes = classes
        self.transform = build_transform(variant, training)

    def __len__(self) -> int:
        return len(self.rows)

    def __getitem__(self, index: int):
        row = self.rows[index]
        with Image.open(ROOT / row["path"]) as image:
            rgb = ImageOps.exif_transpose(image).convert("RGB")
            tensor = self.transform(rgb)
        return tensor, self.classes.index(row["label"]), row["path"]


def evaluate(model: nn.Module, loader: DataLoader, device: str, classes: list[str]) -> tuple[dict, list[dict]]:
    model.eval()
    truth: list[int] = []
    predicted: list[int] = []
    predictions: list[dict] = []
    with torch.inference_mode():
        for images, targets, paths in loader:
            probabilities = torch.softmax(model(images.to(device)), dim=1).cpu()
            batch_predicted = probabilities.argmax(dim=1)
            truth.extend(targets.tolist())
            predicted.extend(batch_predicted.tolist())
            for row_index, path in enumerate(paths):
                true_index = int(targets[row_index])
                predicted_index = int(batch_predicted[row_index])
                record = {
                    "path": path,
                    "true_category": classes[true_index],
                    "true_label": DISPLAY_NAMES[classes[true_index]],
                    "predicted_category": classes[predicted_index],
                    "predicted_label": DISPLAY_NAMES[classes[predicted_index]],
                    "predicted_score": float(probabilities[row_index, predicted_index]),
                    "correct": true_index == predicted_index,
                }
                for class_index, category in enumerate(classes):
                    record[f"score_{category}"] = float(probabilities[row_index, class_index])
                predictions.append(record)
    indexes = list(range(len(classes)))
    precision, recall, class_f1, support = precision_recall_fscore_support(
        truth, predicted, labels=indexes, zero_division=0
    )
    matrix = confusion_matrix(truth, predicted, labels=indexes)
    metrics = {
        "evaluation_split": "val",
        "sample_count": len(truth),
        "error_count": int(sum(actual != guess for actual, guess in zip(truth, predicted))),
        "accuracy_descriptive_only": float(accuracy_score(truth, predicted)),
        "macro_f1_selection_metric": float(
            f1_score(truth, predicted, labels=indexes, average="macro", zero_division=0)
        ),
        "class_order": classes,
        "display_labels": [DISPLAY_NAMES[category] for category in classes],
        "per_class": {
            category: {
                "label": DISPLAY_NAMES[category],
                "precision": float(precision[index]),
                "recall": float(recall[index]),
                "f1": float(class_f1[index]),
                "support": int(support[index]),
            }
            for index, category in enumerate(classes)
        },
        "confusion_matrix_rows_true_columns_predicted": matrix.tolist(),
    }
    return metrics, predictions


def write_validation_outputs(directory: Path, metrics: dict, predictions: list[dict]) -> None:
    write_json(directory / "validation_metrics.json", metrics)
    score_fields = [f"score_{category}" for category in metrics["class_order"]]
    fields = [
        "path",
        "true_category",
        "true_label",
        "predicted_category",
        "predicted_label",
        "predicted_score",
        "correct",
        *score_fields,
    ]
    write_csv(directory / "validation_predictions.csv", predictions, fields)
    errors = [row for row in predictions if not row["correct"]]
    write_csv(directory / "validation_errors.csv", errors, fields)
    grouped: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in errors:
        grouped[(row["true_category"], row["predicted_category"])].append(row)
    error_sample = []
    for pair in sorted(grouped):
        error_sample.extend(sorted(grouped[pair], key=lambda row: row["predicted_score"], reverse=True)[:5])
    write_csv(directory / "validation_error_sample.csv", error_sample, fields)
    matrix = metrics["confusion_matrix_rows_true_columns_predicted"]
    matrix_rows = []
    for row_index, category in enumerate(metrics["class_order"]):
        record = {"true_label": DISPLAY_NAMES[category]}
        for column_index, predicted_category in enumerate(metrics["class_order"]):
            record[f"predicted_{DISPLAY_NAMES[predicted_category]}"] = matrix[row_index][column_index]
        matrix_rows.append(record)
    matrix_fields = ["true_label", *[f"predicted_{DISPLAY_NAMES[c]}" for c in metrics["class_order"]]]
    write_csv(directory / "validation_confusion_matrix.csv", matrix_rows, matrix_fields)


def image_font(size: int, bold: bool = False):
    names = ["arialbd.ttf", "Arial Bold.ttf"] if bold else ["arial.ttf", "Arial.ttf"]
    for name in names:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    return ImageFont.load_default()


def create_preprocessing_figure(experiment_dir: Path, train_rows: list[dict[str, str]]) -> list[dict]:
    by_path = {row["path"]: row for row in train_rows}
    missing = [path for path in VISUAL_EXAMPLES if path not in by_path]
    if missing:
        raise RuntimeError(f"Los ejemplos visuales no pertenecen a TRAIN: {missing}")

    cell_width, image_size, row_height, header_height = 280, 224, 300, 70
    canvas = Image.new("RGB", (cell_width * 3, header_height + row_height * len(VISUAL_EXAMPLES)), (246, 240, 223))
    draw = ImageDraw.Draw(canvas)
    title_font = image_font(19, bold=True)
    text_font = image_font(15)
    small_font = image_font(12)
    headers = ("Original 1920x1080", "Control 224x224", "Candidato 224x224")
    for column, header in enumerate(headers):
        draw.text((column * cell_width + 24, 24), header, fill=(22, 63, 49), font=title_font)

    records = []
    for row_index, path_string in enumerate(VISUAL_EXAMPLES):
        row = by_path[path_string]
        with Image.open(ROOT / path_string) as source:
            original = ImageOps.exif_transpose(source).convert("RGB")
            control = geometry_transform("control")(original)
            candidate = geometry_transform("candidate")(original)
        versions = []
        original_preview = original.copy()
        original_preview.thumbnail((image_size, image_size), Image.Resampling.BILINEAR)
        versions.append(original_preview)
        versions.extend([control, candidate])
        y = header_height + row_index * row_height
        for column, version in enumerate(versions):
            x = column * cell_width + (cell_width - version.width) // 2
            image_y = y + 24 + (image_size - version.height) // 2
            canvas.paste(version, (x, image_y))
            draw.rectangle(
                (column * cell_width + 27, y + 23, column * cell_width + 27 + image_size, y + 23 + image_size),
                outline=(82, 103, 95),
                width=1,
            )
        label = f"{DISPLAY_NAMES[row['label']]} · TRAIN · {Path(path_string).name}"
        draw.text((24, y + 257), label, fill=(69, 95, 85), font=text_font)
        draw.text((584, y + 278), "Relleno RGB 124,116,104", fill=(123, 56, 37), font=small_font)
        geometry = AspectPadToSquare().geometry(*original.size)
        records.append(
            {
                "path": path_string,
                "split": row["split"],
                "category": row["label"],
                "original_mode": original.mode,
                "original_size_width_height": list(original.size),
                "control_size_width_height": list(control.size),
                "candidate_size_width_height": list(candidate.size),
                "candidate_geometry": geometry,
            }
        )
    output = experiment_dir / "preprocessing_comparison_train.png"
    canvas.save(output, format="PNG")
    write_json(experiment_dir / "preprocessing_examples.json", records)
    return records


def check_tensors(experiment_dir: Path, train_rows: list[dict[str, str]], classes: list[str]) -> dict:
    by_path = {row["path"]: row for row in train_rows}
    results = []
    for path_string in VISUAL_EXAMPLES:
        with Image.open(ROOT / path_string) as source:
            rgb = ImageOps.exif_transpose(source).convert("RGB")
            for variant in ("control", "candidate"):
                tensor = build_transform(variant, training=False)(rgb)
                inverse = torch.empty_like(tensor)
                for channel in range(3):
                    inverse[channel] = tensor[channel] * IMAGENET_STD[channel] + IMAGENET_MEAN[channel]
                record = {
                    "path": path_string,
                    "variant": variant,
                    "input_mode_after_conversion": rgb.mode,
                    "tensor_shape_channels_height_width": list(tensor.shape),
                    "tensor_dtype": str(tensor.dtype),
                    "all_values_finite": bool(torch.isfinite(tensor).all()),
                    "normalized_channel_mean": [float(value) for value in tensor.mean(dim=(1, 2))],
                    "normalized_channel_std": [float(value) for value in tensor.std(dim=(1, 2))],
                    "inverse_normalized_min": float(inverse.min()),
                    "inverse_normalized_max": float(inverse.max()),
                }
                if variant == "candidate":
                    record["top_left_normalized_rgb"] = [float(value) for value in tensor[:, 0, 0]]
                    record["expected_padding_normalized_rgb"] = [
                        (PADDING_RGB[index] / 255 - IMAGENET_MEAN[index]) / IMAGENET_STD[index]
                        for index in range(3)
                    ]
                if list(tensor.shape) != [3, 224, 224] or tensor.dtype != torch.float32:
                    raise RuntimeError(f"Tensor inesperado: {record}")
                if not record["all_values_finite"]:
                    raise RuntimeError(f"Tensor no finito: {record}")
                if record["inverse_normalized_min"] < -1e-6 or record["inverse_normalized_max"] > 1 + 1e-6:
                    raise RuntimeError(f"La inversión de normalización quedó fuera de [0,1]: {record}")
                results.append(record)

    source_model, metadata = load_checkpoint(SOURCE_CHECKPOINT)
    if metadata["classes"] != classes:
        raise RuntimeError("El orden de clases del checkpoint no coincide con el manifiesto")
    sample_dataset = BranchLeaves([by_path[path] for path in VISUAL_EXAMPLES], classes, "candidate", False)
    batch = torch.stack([sample_dataset[index][0] for index in range(len(sample_dataset))])
    with torch.inference_mode():
        output_shape = list(source_model(batch).shape)
    if output_shape != [len(VISUAL_EXAMPLES), len(classes)]:
        raise RuntimeError(f"Salida del modelo inesperada: {output_shape}")
    summary = {
        "status": "passed",
        "examples_are_train_only": True,
        "test_images_opened": False,
        "class_order": classes,
        "model_input_batch_shape": list(batch.shape),
        "model_output_shape": output_shape,
        "records": results,
    }
    write_json(experiment_dir / "tensor_preflight.json", summary)
    return summary


def metrics_close(actual: dict, expected: dict, tolerance: float = 1e-12) -> bool:
    if abs(actual["macro_f1_selection_metric"] - expected["macro_f1_selection_metric"]) > tolerance:
        return False
    if abs(actual["accuracy_descriptive_only"] - expected["accuracy_descriptive_only"]) > tolerance:
        return False
    if actual["confusion_matrix_rows_true_columns_predicted"] != expected["confusion_matrix_rows_true_columns_predicted"]:
        return False
    for category in actual["class_order"]:
        for metric in ("precision", "recall", "f1"):
            if abs(actual["per_class"][category][metric] - expected["per_class"][category][metric]) > tolerance:
                return False
    return True


def legacy_initial_metrics_close(actual: dict, expected: dict, tolerance: float = 1e-12) -> bool:
    if abs(actual["macro_f1_selection_metric"] - expected["macro_f1"]) > tolerance:
        return False
    if actual["confusion_matrix_rows_true_columns_predicted"] != expected["confusion_matrix_rows_true_columns_predicted"]:
        return False
    for index, category in enumerate(actual["class_order"]):
        for metric in ("precision", "recall", "f1"):
            if abs(actual["per_class"][category][metric] - expected[metric][index]) > tolerance:
                return False
    return True


def prepare_control_reuse(
    experiment_dir: Path,
    train_rows: list[dict[str, str]],
    val_rows: list[dict[str, str]],
    classes: list[str],
) -> dict:
    control_dir = experiment_dir / "control"
    required = [
        "configuration.json",
        "history.json",
        "best_checkpoint.pt",
        "candidate_initial_epoch0.pt",
        "initial_validation_metrics.json",
        "validation_metrics.json",
        "summary.json",
        "optimizer_check.json",
        "gradient_check.json",
        "batch_norm_check.json",
    ]
    missing = [name for name in required if not (CONTROL_SOURCE_DIR / name).is_file()]
    if missing:
        raise FileNotFoundError(f"Faltan evidencias del control reutilizable: {missing}")
    source_config = json.loads((CONTROL_SOURCE_DIR / "configuration.json").read_text(encoding="utf-8"))
    source_summary = json.loads((CONTROL_SOURCE_DIR / "summary.json").read_text(encoding="utf-8"))
    history = json.loads((CONTROL_SOURCE_DIR / "history.json").read_text(encoding="utf-8"))
    expected_initial = json.loads((CONTROL_SOURCE_DIR / "initial_validation_metrics.json").read_text(encoding="utf-8"))
    expected_best = json.loads((CONTROL_SOURCE_DIR / "validation_metrics.json").read_text(encoding="utf-8"))

    configuration_checks = {
        "source_checkpoint_sha256": source_config["source_checkpoint_sha256"] == EXPECTED_SOURCE_SHA256,
        "manifest_sha256": source_config["manifest_sha256"] == EXPECTED_MANIFEST_SHA256,
        "seed": source_config["seed"] == SEED,
        "train_images": source_config["train_images"] == len(train_rows),
        "validation_images": source_config["validation_images"] == len(val_rows),
        "batch_size": source_config["batch_size"] == BATCH_SIZE,
        "maximum_epochs": source_config["maximum_epochs"] == MAX_EPOCHS,
        "early_stopping_patience": source_config["early_stopping_patience"] == PATIENCE,
        "selection_metric": source_config["selection_metric"] == "validation macro F1",
        "optimizer": source_config["optimizer"] == "Adam",
        "feature_learning_rate": source_config["learning_rates"]["features_last_three"] == FEATURE_LEARNING_RATE,
        "classifier_learning_rate": source_config["learning_rates"]["classifier_last"] == CLASSIFIER_LEARNING_RATE,
        "unfrozen_feature_modules": source_config["unfrozen_feature_module_indexes"] == [10, 11, 12],
        "batch_norm_statistics_frozen": source_config["batch_norm_running_statistics_frozen"] is True,
        "batch_norm_affine_trainable": source_config["batch_norm_affine_parameters_in_unfrozen_modules_trainable"] is True,
        "class_weights": source_config["class_weights"]
        == {
            "coffee___healthy": 0.6547619047619048,
            "coffee___red_spider_mite": 3.154121863799283,
            "coffee___rust": 0.8652900688298918,
        },
        "augmentation_order": source_config["training_augmentation"]
        == ["RandomHorizontalFlip", "RandomRotation(15 degrees)"],
        "test_not_used": source_config["test_used"] is False,
    }
    if not all(configuration_checks.values()):
        raise RuntimeError(f"La configuración del control no es equivalente: {configuration_checks}")
    if sha256(CONTROL_SOURCE_DIR / "candidate_initial_epoch0.pt") != EXPECTED_SOURCE_SHA256:
        raise RuntimeError("La copia inicial del control no coincide con el checkpoint común")
    if sha256(CONTROL_SOURCE_DIR / "best_checkpoint.pt") != EXPECTED_ACTIVE_SHA256:
        raise RuntimeError("El mejor checkpoint del control no coincide con el archivo esperado")

    legacy_eval = legacy_transform(training=False)
    explicit_eval = build_transform("control", training=False)
    evaluation_tensor_matches = 0
    for row in val_rows:
        with Image.open(ROOT / row["path"]) as image:
            rgb = ImageOps.exif_transpose(image).convert("RGB")
            if not torch.equal(legacy_eval(rgb), explicit_eval(rgb)):
                raise RuntimeError(f"El control explícito difiere del legado en VAL: {row['path']}")
        evaluation_tensor_matches += 1

    legacy_train = legacy_transform(training=True)
    explicit_train = build_transform("control", training=True)
    training_tensor_checks = 0
    for path_string in VISUAL_EXAMPLES:
        with Image.open(ROOT / path_string) as image:
            rgb = ImageOps.exif_transpose(image).convert("RGB")
            for check_seed in range(10):
                torch.manual_seed(check_seed)
                legacy_tensor = legacy_train(rgb)
                torch.manual_seed(check_seed)
                explicit_tensor = explicit_train(rgb)
                if not torch.equal(legacy_tensor, explicit_tensor):
                    raise RuntimeError(f"El aumento explícito difiere del legado: {path_string}, semilla {check_seed}")
                training_tensor_checks += 1
    validation_loader = DataLoader(
        BranchLeaves(val_rows, classes, "control", False),
        batch_size=BATCH_SIZE,
        shuffle=False,
        num_workers=0,
    )
    device = "cuda" if torch.cuda.is_available() else "cpu"
    initial_model, _ = load_checkpoint(CONTROL_SOURCE_DIR / "candidate_initial_epoch0.pt")
    initial_metrics, _ = evaluate(initial_model.to(device), validation_loader, device, classes)
    best_model, _ = load_checkpoint(CONTROL_SOURCE_DIR / "best_checkpoint.pt")
    best_metrics, _ = evaluate(best_model.to(device), validation_loader, device, classes)
    if not legacy_initial_metrics_close(initial_metrics, expected_initial):
        raise RuntimeError("Las métricas iniciales del control no se reprodujeron")
    if not metrics_close(best_metrics, expected_best):
        raise RuntimeError("Las métricas seleccionadas del control no se reprodujeron")

    for source in CONTROL_SOURCE_DIR.iterdir():
        if source.is_file():
            shutil.copy2(source, control_dir / source.name)
    branch_config = {
        "branch": "A_control_reused",
        "source_experiment": relative(CONTROL_SOURCE_DIR),
        "same_initial_checkpoint_as_candidate": True,
        "source_checkpoint": relative(SOURCE_CHECKPOINT),
        "source_checkpoint_sha256": EXPECTED_SOURCE_SHA256,
        "preprocessing": preprocessing_config("control"),
        "duration_seconds": source_summary["duration_seconds"],
        "epochs_run": source_summary["epochs_run"],
        "selected_epoch": source_summary["selected_candidate_epoch"],
        "selected_checkpoint_sha256": sha256(CONTROL_SOURCE_DIR / "best_checkpoint.pt"),
    }
    write_json(control_dir / "branch_configuration.json", branch_config)
    equivalence = {
        "status": "passed",
        "reused": True,
        "configuration_checks": configuration_checks,
        "validation_tensors_equal_legacy_vs_explicit": evaluation_tensor_matches,
        "training_augmentation_tensor_checks_equal": training_tensor_checks,
        "initial_metrics_reproduced": True,
        "selected_metrics_reproduced": True,
        "initial_macro_f1": initial_metrics["macro_f1_selection_metric"],
        "selected_macro_f1": best_metrics["macro_f1_selection_metric"],
        "history_records": len(history),
        "device_for_reproduction": device,
    }
    write_json(control_dir / "reuse_equivalence.json", equivalence)
    return equivalence


def preflight() -> Path:
    before = integrity_snapshot()
    require_expected_integrity(before)
    rows = read_rows()
    train_rows = [row for row in rows if row["split"] == "train"]
    val_rows = [row for row in rows if row["split"] == "val"]
    classes = sorted({row["label"] for row in train_rows + val_rows})
    if classes != list(DISPLAY_NAMES):
        raise RuntimeError(f"Orden de clases inesperado: {classes}")
    if len(train_rows) != 880 or len(val_rows) != 301:
        raise RuntimeError("Conteos TRAIN/VAL inesperados")

    experiment_dir = new_experiment_dir()
    shutil.copy2(ROOT / "reports" / "V2_EXPERIMENT_PROTOCOL.md", experiment_dir / "protocol_snapshot.md")
    visual_records = create_preprocessing_figure(experiment_dir, train_rows)
    tensor_check = check_tensors(experiment_dir, train_rows, classes)
    equivalence = prepare_control_reuse(experiment_dir, train_rows, val_rows, classes)
    after = integrity_snapshot()
    require_expected_integrity(after)
    if after != before:
        raise RuntimeError("Un archivo activo cambió durante el preflight")
    write_json(experiment_dir / "active_files_before.json", before)
    write_json(experiment_dir / "active_files_after_preflight.json", after)
    experiment = {
        "status": "preflight_complete",
        "created_at": datetime.now().astimezone().isoformat(),
        "experiment": "paired MobileNet v2 preprocessing control vs aspect-preserving padding",
        "source_checkpoint": relative(SOURCE_CHECKPOINT),
        "source_checkpoint_sha256": EXPECTED_SOURCE_SHA256,
        "manifest_sha256": EXPECTED_MANIFEST_SHA256,
        "active_web_checkpoint_unchanged": True,
        "active_web_checkpoint_sha256": EXPECTED_ACTIVE_SHA256,
        "test_images_opened": False,
        "test_evaluated": False,
        "uncertainty_threshold_changed": False,
        "seed": SEED,
        "train_images": len(train_rows),
        "validation_images": len(val_rows),
        "class_order": classes,
        "control": {"mode": "reused_after_exact_equivalence_checks", "equivalence": equivalence},
        "candidate": {"mode": "pending_training", "preprocessing": preprocessing_config("candidate")},
        "visual_examples": visual_records,
        "tensor_preflight_status": tensor_check["status"],
        "software": {
            "python": __import__("sys").version,
            "torch": torch.__version__,
            "torchvision": torchvision.__version__,
            "pillow": PIL.__version__,
            "numpy": np.__version__,
        },
    }
    write_json(experiment_dir / "experiment.json", experiment)
    print(f"EXPERIMENT_DIR={relative(experiment_dir)}", flush=True)
    print(json.dumps({"status": experiment["status"], "control_equivalence": equivalence["status"]}, ensure_ascii=False), flush=True)
    return experiment_dir


def freeze_batch_norm_statistics(model: nn.Module) -> None:
    for module in model.modules():
        if isinstance(module, nn.modules.batchnorm._BatchNorm):
            module.eval()


def batch_norm_state(model: nn.Module) -> dict[str, dict[str, torch.Tensor]]:
    return {
        name: {
            "running_mean": module.running_mean.detach().cpu().clone(),
            "running_var": module.running_var.detach().cpu().clone(),
            "num_batches_tracked": module.num_batches_tracked.detach().cpu().clone(),
        }
        for name, module in model.named_modules()
        if isinstance(module, nn.modules.batchnorm._BatchNorm)
    }


def state_dict_cpu(model: nn.Module) -> dict[str, torch.Tensor]:
    return {name: value.detach().cpu().clone() for name, value in model.state_dict().items()}


def train_candidate(experiment_dir: Path) -> None:
    experiment_path = experiment_dir / "experiment.json"
    if not experiment_path.is_file():
        raise FileNotFoundError("La carpeta no contiene un preflight")
    experiment = json.loads(experiment_path.read_text(encoding="utf-8"))
    if experiment["status"] != "preflight_complete":
        raise RuntimeError(f"Estado de experimento inesperado: {experiment['status']}")
    before = integrity_snapshot()
    require_expected_integrity(before)
    expected_before = json.loads((experiment_dir / "active_files_before.json").read_text(encoding="utf-8"))
    if before != expected_before:
        raise RuntimeError("Los archivos activos cambiaron después del preflight")

    random.seed(SEED)
    np.random.seed(SEED)
    torch.manual_seed(SEED)
    rows = read_rows()
    train_rows = [row for row in rows if row["split"] == "train"]
    val_rows = [row for row in rows if row["split"] == "val"]
    classes = experiment["class_order"]
    train_loader = DataLoader(
        BranchLeaves(train_rows, classes, "candidate", True),
        batch_size=BATCH_SIZE,
        shuffle=True,
        num_workers=0,
    )
    val_loader = DataLoader(
        BranchLeaves(val_rows, classes, "candidate", False),
        batch_size=BATCH_SIZE,
        shuffle=False,
        num_workers=0,
    )
    model, source_metadata = load_checkpoint(SOURCE_CHECKPOINT)
    if source_metadata["model"] != "mobilenet":
        raise RuntimeError("El checkpoint inicial no es MobileNet")
    if source_metadata["classes"] != classes:
        raise RuntimeError("El orden de clases del checkpoint cambió")
    if source_metadata["seed"] != SEED or source_metadata["manifest_sha256"] != EXPECTED_MANIFEST_SHA256:
        raise RuntimeError("El checkpoint inicial no corresponde a la semilla o manifiesto fijados")
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = model.to(device)
    initial_metrics, _ = evaluate(model, val_loader, device, classes)
    candidate_dir = experiment_dir / "candidate"
    shutil.copy2(SOURCE_CHECKPOINT, candidate_dir / "candidate_initial_epoch0.pt")
    write_json(candidate_dir / "initial_validation_metrics.json", initial_metrics)

    for parameter in model.parameters():
        parameter.requires_grad = False
    feature_indexes = list(range(len(model.features) - 3, len(model.features)))
    for index in feature_indexes:
        for parameter in model.features[index].parameters():
            parameter.requires_grad = True
    for parameter in model.classifier[-1].parameters():
        parameter.requires_grad = True
    named_parameters = dict(model.named_parameters())
    trainable_names = [name for name, parameter in named_parameters.items() if parameter.requires_grad]
    feature_names = [name for name in trainable_names if name.startswith("features.")]
    classifier_names = [name for name in trainable_names if name.startswith("classifier.3.")]
    if not feature_names or set(classifier_names) != {"classifier.3.weight", "classifier.3.bias"}:
        raise RuntimeError("Configuración de capas entrenables inesperada")
    feature_parameters = [named_parameters[name] for name in feature_names]
    classifier_parameters = [named_parameters[name] for name in classifier_names]
    optimizer = torch.optim.Adam(
        [
            {"params": feature_parameters, "lr": FEATURE_LEARNING_RATE, "name": "features_last_three"},
            {"params": classifier_parameters, "lr": CLASSIFIER_LEARNING_RATE, "name": "classifier_last"},
        ]
    )
    optimizer_ids = {id(parameter) for group in optimizer.param_groups for parameter in group["params"]}
    trainable_ids = {id(parameter) for parameter in model.parameters() if parameter.requires_grad}
    optimizer_check = {
        "all_trainable_parameters_in_optimizer": optimizer_ids == trainable_ids,
        "no_frozen_parameters_in_optimizer": all(
            parameter.requires_grad for group in optimizer.param_groups for parameter in group["params"]
        ),
        "groups": [
            {
                "name": group["name"],
                "learning_rate": group["lr"],
                "parameter_count": sum(parameter.numel() for parameter in group["params"]),
            }
            for group in optimizer.param_groups
        ],
    }
    if not all([optimizer_check["all_trainable_parameters_in_optimizer"], optimizer_check["no_frozen_parameters_in_optimizer"]]):
        raise RuntimeError("El optimizador no coincide con las capas descongeladas")
    write_json(candidate_dir / "optimizer_check.json", optimizer_check)

    counts = np.array([sum(row["label"] == category for row in train_rows) for category in classes])
    class_weights = len(train_rows) / (len(classes) * counts)
    criterion = nn.CrossEntropyLoss(
        weight=torch.tensor(class_weights, dtype=torch.float32, device=device)
    )
    bn_before = batch_norm_state(model)
    trainable_conv_names = []
    for module_name, module in model.named_modules():
        if isinstance(module, nn.Conv2d):
            for parameter_name, _ in module.named_parameters(recurse=False):
                full_name = f"{module_name}.{parameter_name}"
                if full_name in trainable_names:
                    trainable_conv_names.append(full_name)

    configuration = {
        "status": "running",
        "branch": "B_candidate_aspect_preserving_padding",
        "source_checkpoint": relative(SOURCE_CHECKPOINT),
        "source_checkpoint_sha256": EXPECTED_SOURCE_SHA256,
        "manifest_sha256": EXPECTED_MANIFEST_SHA256,
        "same_initial_checkpoint_as_control": True,
        "seed": SEED,
        "train_images": len(train_rows),
        "validation_images": len(val_rows),
        "test_used": False,
        "batch_size": BATCH_SIZE,
        "maximum_epochs": MAX_EPOCHS,
        "early_stopping_patience": PATIENCE,
        "selection_metric": "validation macro F1",
        "optimizer": "Adam",
        "learning_rates": {
            "features_last_three": FEATURE_LEARNING_RATE,
            "classifier_last": CLASSIFIER_LEARNING_RATE,
        },
        "unfrozen_feature_module_indexes": feature_indexes,
        "trainable_parameter_names": trainable_names,
        "trainable_parameters": sum(parameter.numel() for parameter in model.parameters() if parameter.requires_grad),
        "total_parameters": sum(parameter.numel() for parameter in model.parameters()),
        "batch_norm_running_statistics_frozen": True,
        "batch_norm_affine_parameters_in_unfrozen_modules_trainable": True,
        "loss": "weighted cross entropy; class weights calculated only from train",
        "class_weights": {category: float(class_weights[index]) for index, category in enumerate(classes)},
        "preprocessing": preprocessing_config("candidate"),
        "uncertainty_threshold_used_for_selection": False,
        "uncertainty_threshold_unchanged": 0.70,
        "device": device,
    }
    write_json(candidate_dir / "configuration.json", configuration)
    write_json(candidate_dir / "preprocessing.json", preprocessing_config("candidate"))

    best_score = initial_metrics["macro_f1_selection_metric"]
    best_epoch = 0
    best_state = state_dict_cpu(model)
    history = [
        {
            "candidate_epoch": 0,
            "train_loss": None,
            "val_macro_f1": best_score,
            "improved_over_best": False,
            "consecutive_epochs_without_improvement": 0,
        }
    ]
    write_json(candidate_dir / "history.json", history)
    epochs_without_improvement = 0
    gradient_check = None
    started = time.perf_counter()
    for epoch in range(1, MAX_EPOCHS + 1):
        model.train()
        freeze_batch_norm_statistics(model)
        total_loss = 0.0
        for batch_index, (images, targets, _) in enumerate(train_loader):
            images, targets = images.to(device), targets.to(device)
            optimizer.zero_grad()
            loss = criterion(model(images), targets)
            loss.backward()
            if gradient_check is None:
                gradient_records = {
                    name: {
                        "gradient_present": parameter.grad is not None,
                        "gradient_norm": float(parameter.grad.detach().norm().cpu()) if parameter.grad is not None else None,
                    }
                    for name, parameter in named_parameters.items()
                    if parameter.requires_grad
                }
                gradient_check = {
                    "checked_epoch": epoch,
                    "checked_batch": batch_index + 1,
                    "all_trainable_parameters_have_gradients": all(
                        record["gradient_present"] for record in gradient_records.values()
                    ),
                    "all_unfrozen_convolution_parameters_have_nonzero_gradients": all(
                        gradient_records[name]["gradient_present"] and gradient_records[name]["gradient_norm"] > 0
                        for name in trainable_conv_names
                    ),
                    "unfrozen_convolution_parameter_names": sorted(trainable_conv_names),
                    "parameters": gradient_records,
                }
                if not gradient_check["all_trainable_parameters_have_gradients"] or not gradient_check["all_unfrozen_convolution_parameters_have_nonzero_gradients"]:
                    raise RuntimeError("Falló la comprobación de gradientes")
                write_json(candidate_dir / "gradient_check.json", gradient_check)
            optimizer.step()
            total_loss += float(loss.item()) * len(targets)
        validation, _ = evaluate(model, val_loader, device, classes)
        improved = validation["macro_f1_selection_metric"] > best_score
        if improved:
            best_score = validation["macro_f1_selection_metric"]
            best_epoch = epoch
            best_state = state_dict_cpu(model)
            epochs_without_improvement = 0
        else:
            epochs_without_improvement += 1
        record = {
            "candidate_epoch": epoch,
            "train_loss": total_loss / len(train_rows),
            "val_macro_f1": validation["macro_f1_selection_metric"],
            "improved_over_best": improved,
            "consecutive_epochs_without_improvement": epochs_without_improvement,
        }
        history.append(record)
        write_json(candidate_dir / "history.json", history)
        print(json.dumps(record, ensure_ascii=False), flush=True)
        if epochs_without_improvement >= PATIENCE:
            break
    duration_seconds = time.perf_counter() - started

    bn_after = batch_norm_state(model)
    bn_checks = {
        name: {key: bool(torch.equal(bn_before[name][key], bn_after[name][key])) for key in bn_before[name]}
        for name in bn_before
    }
    batch_norm_check = {
        "all_running_statistics_unchanged": all(all(values.values()) for values in bn_checks.values()),
        "batch_norm_modules": bn_checks,
    }
    if not batch_norm_check["all_running_statistics_unchanged"]:
        raise RuntimeError("Las estadísticas BatchNorm cambiaron")
    write_json(candidate_dir / "batch_norm_check.json", batch_norm_check)

    checkpoint = {
        "state_dict": best_state,
        "classes": classes,
        "model": "mobilenet",
        "val_macro_f1": best_score,
        "manifest_sha256": EXPECTED_MANIFEST_SHA256,
        "seed": SEED,
        "epochs": len(history) - 1,
        "selected_candidate_epoch": best_epoch,
        "source_checkpoint_sha256": EXPECTED_SOURCE_SHA256,
        "trainable_parameter_names": trainable_names,
        "fine_tuning": {
            "unfrozen_feature_module_indexes": feature_indexes,
            "feature_learning_rate": FEATURE_LEARNING_RATE,
            "classifier_learning_rate": CLASSIFIER_LEARNING_RATE,
            "batch_norm_running_statistics_frozen": True,
            "early_stopping_patience": PATIENCE,
        },
        "preprocessing": preprocessing_config("candidate"),
        "preprocessing_id": preprocessing_config("candidate")["id"],
    }
    best_checkpoint_path = candidate_dir / "best_checkpoint.pt"
    torch.save(checkpoint, best_checkpoint_path)
    model.load_state_dict(best_state)
    selected_metrics, selected_predictions = evaluate(model, val_loader, device, classes)
    selected_metrics.update(
        {
            "checkpoint": {
                "path": relative(best_checkpoint_path),
                "sha256": sha256(best_checkpoint_path),
                "selected_epoch": best_epoch,
                "source_checkpoint_sha256": EXPECTED_SOURCE_SHA256,
            },
            "manifest_sha256": EXPECTED_MANIFEST_SHA256,
            "preprocessing": preprocessing_config("candidate"),
        }
    )
    write_validation_outputs(candidate_dir, selected_metrics, selected_predictions)
    summary = {
        "status": "complete",
        "selected_candidate_epoch": best_epoch,
        "initial_validation_macro_f1_under_candidate_preprocessing": initial_metrics["macro_f1_selection_metric"],
        "best_validation_macro_f1": best_score,
        "epochs_run": len(history) - 1,
        "stopped_early": len(history) - 1 < MAX_EPOCHS,
        "duration_seconds": duration_seconds,
        "selected_checkpoint": "best_checkpoint.pt",
        "selected_checkpoint_sha256": selected_metrics["checkpoint"]["sha256"],
        "preprocessing_id": preprocessing_config("candidate")["id"],
        "test_used": False,
    }
    write_json(candidate_dir / "summary.json", summary)
    configuration.update(
        {
            "status": "complete",
            "epochs_run": summary["epochs_run"],
            "selected_candidate_epoch": best_epoch,
            "best_validation_macro_f1": best_score,
            "duration_seconds": duration_seconds,
            "selected_checkpoint_sha256": summary["selected_checkpoint_sha256"],
        }
    )
    write_json(candidate_dir / "configuration.json", configuration)

    final_integrity = integrity_snapshot()
    require_expected_integrity(final_integrity)
    if final_integrity != before:
        raise RuntimeError("Un archivo activo cambió durante el entrenamiento")
    write_json(experiment_dir / "active_files_after_training.json", final_integrity)
    write_comparison(experiment_dir)
    experiment.update(
        {
            "status": "complete",
            "completed_at": datetime.now().astimezone().isoformat(),
            "candidate": {
                "mode": "trained_once",
                "preprocessing": preprocessing_config("candidate"),
                "summary": summary,
            },
            "active_web_checkpoint_unchanged": True,
            "test_images_opened": False,
            "test_evaluated": False,
        }
    )
    write_json(experiment_path, experiment)
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)


def write_comparison(experiment_dir: Path) -> None:
    control_metrics = json.loads((experiment_dir / "control" / "validation_metrics.json").read_text(encoding="utf-8"))
    candidate_metrics = json.loads((experiment_dir / "candidate" / "validation_metrics.json").read_text(encoding="utf-8"))
    control_summary = json.loads((experiment_dir / "control" / "summary.json").read_text(encoding="utf-8"))
    candidate_summary = json.loads((experiment_dir / "candidate" / "summary.json").read_text(encoding="utf-8"))
    classes = control_metrics["class_order"]
    if candidate_metrics["class_order"] != classes:
        raise RuntimeError("El orden de clases difiere entre ramas")
    class_differences = {}
    for category in classes:
        class_differences[category] = {
            metric: candidate_metrics["per_class"][category][metric]
            - control_metrics["per_class"][category][metric]
            for metric in ("precision", "recall", "f1")
        }
    mite_index = classes.index("coffee___red_spider_mite")
    rust_index = classes.index("coffee___rust")
    healthy_index = classes.index("coffee___healthy")
    control_matrix = control_metrics["confusion_matrix_rows_true_columns_predicted"]
    candidate_matrix = candidate_metrics["confusion_matrix_rows_true_columns_predicted"]
    comparison = {
        "scope": "validation only",
        "test_used": False,
        "same_initial_checkpoint": True,
        "source_checkpoint_sha256": EXPECTED_SOURCE_SHA256,
        "manifest_sha256": EXPECTED_MANIFEST_SHA256,
        "seed": SEED,
        "control_reused_after_equivalence_check": True,
        "macro_f1": {
            "control": control_metrics["macro_f1_selection_metric"],
            "candidate": candidate_metrics["macro_f1_selection_metric"],
            "candidate_minus_control": candidate_metrics["macro_f1_selection_metric"]
            - control_metrics["macro_f1_selection_metric"],
        },
        "per_class_candidate_minus_control": class_differences,
        "requested_error_counts": {
            "mite_to_rust": {
                "control": control_matrix[mite_index][rust_index],
                "candidate": candidate_matrix[mite_index][rust_index],
                "candidate_minus_control": candidate_matrix[mite_index][rust_index]
                - control_matrix[mite_index][rust_index],
            },
            "rust_to_healthy": {
                "control": control_matrix[rust_index][healthy_index],
                "candidate": candidate_matrix[rust_index][healthy_index],
                "candidate_minus_control": candidate_matrix[rust_index][healthy_index]
                - control_matrix[rust_index][healthy_index],
            },
        },
        "control": {
            "metrics": control_metrics,
            "epochs_run": control_summary["epochs_run"],
            "selected_epoch": control_summary["selected_candidate_epoch"],
            "duration_seconds": control_summary["duration_seconds"],
        },
        "candidate": {
            "metrics": candidate_metrics,
            "epochs_run": candidate_summary["epochs_run"],
            "selected_epoch": candidate_summary["selected_candidate_epoch"],
            "duration_seconds": candidate_summary["duration_seconds"],
        },
        "interpretation_limit": "Una sola semilla no demuestra que una diferencia pequeña sea consistente.",
    }
    write_json(experiment_dir / "comparison.json", comparison)
    rows = []
    for branch, metrics in (("control", control_metrics), ("candidate", candidate_metrics)):
        rows.append(
            {
                "branch": branch,
                "metric_scope": "overall",
                "class": "macro",
                "precision": "",
                "recall": "",
                "f1": metrics["macro_f1_selection_metric"],
                "support": metrics["sample_count"],
            }
        )
        for category in classes:
            row = metrics["per_class"][category]
            rows.append(
                {
                    "branch": branch,
                    "metric_scope": "class",
                    "class": DISPLAY_NAMES[category],
                    "precision": row["precision"],
                    "recall": row["recall"],
                    "f1": row["f1"],
                    "support": row["support"],
                }
            )
    write_csv(
        experiment_dir / "comparison.csv",
        rows,
        ["branch", "metric_scope", "class", "precision", "recall", "f1", "support"],
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Experimento pareado de preprocesamiento CaféIA v2")
    parser.add_argument("--stage", choices=("preflight", "train"), required=True)
    parser.add_argument("--experiment-dir", type=Path)
    args = parser.parse_args()
    if args.stage == "preflight":
        if args.experiment_dir is not None:
            parser.error("preflight crea automáticamente una carpeta nueva")
        preflight()
        return
    if args.experiment_dir is None:
        parser.error("train exige --experiment-dir")
    experiment_dir = args.experiment_dir if args.experiment_dir.is_absolute() else ROOT / args.experiment_dir
    train_candidate(experiment_dir)


if __name__ == "__main__":
    main()
