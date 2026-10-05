"""Experimento pareado de profundidad de ajuste fino, limitado a TRAIN/VAL.

Ejecuta control y candidato desde el mismo checkpoint para tres semillas. No
abre imágenes de TEST, no modifica checkpoints activos y conserva cada corrida.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import shutil
import statistics
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import torch
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, precision_recall_fscore_support
from torch import nn
from torch.utils.data import DataLoader

from src.common import ROOT, Leaves, load_checkpoint


SOURCE_CHECKPOINT = ROOT / "experiments" / "mobilenet_finetune_20260922-103426" / "candidate_initial_epoch0.pt"
EXPECTED_SOURCE_SHA256 = "9248cc767425c9efec643bcc2cabd758e8f2b28ab4a6967908713fc1d0b9c5c1"
EXPECTED_MANIFEST_SHA256 = "1ea21d6b2b480b830065c5d4d1d90f531234cc2aa244d7bb98c5873363866dab"
ACTIVE_PATHS = (
    ROOT / "models" / "mobilenet.pt",
    ROOT / "models" / "mobilenet_finetuned_epoch6.pt",
    ROOT / "data" / "processed" / "manifest.csv",
)
SEEDS = (42, 43, 44)
BRANCHES = {
    "control": (10, 11, 12),
    "candidate": (7, 8, 9, 10, 11, 12),
}
FEATURE_LR = 1e-5
CLASSIFIER_LR = 1e-4
MAX_EPOCHS = 15
PATIENCE = 4
BATCH_SIZE = 16
MIN_MEAN_MACRO_F1_GAIN = 0.010
MAX_MEAN_CLASS_RECALL_DROP = 0.020
DISPLAY_NAMES = {
    "coffee___healthy": "Hoja sana",
    "coffee___red_spider_mite": "Ácaro rojo",
    "coffee___rust": "Roya",
}


def digest(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def relative(path: Path) -> str:
    return str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)


def snapshot(paths: tuple[Path, ...]) -> list[dict[str, Any]]:
    return [
        {"path": relative(path), "bytes": path.stat().st_size, "sha256": digest(path)}
        for path in paths
    ]


def read_train_val() -> tuple[list[dict[str, str]], list[dict[str, str]], Counter[str]]:
    manifest = ROOT / "data" / "processed" / "manifest.csv"
    train: list[dict[str, str]] = []
    val: list[dict[str, str]] = []
    skipped = Counter()
    with manifest.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            split = row["split"]
            if split == "train":
                train.append(row)
            elif split == "val":
                val.append(row)
            else:
                # No se conservan ni se usan rutas, etiquetas o hashes de TEST.
                skipped[split] += 1
    return train, val, skipped


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


def configure_trainable(model: nn.Module, indexes: tuple[int, ...]) -> tuple[list[str], list[str], list[str]]:
    for parameter in model.parameters():
        parameter.requires_grad = False
    for index in indexes:
        for parameter in model.features[index].parameters():
            parameter.requires_grad = True
    for parameter in model.classifier[-1].parameters():
        parameter.requires_grad = True

    named = dict(model.named_parameters())
    trainable = [name for name, parameter in named.items() if parameter.requires_grad]
    features = [name for name in trainable if name.startswith("features.")]
    classifier = [name for name in trainable if name.startswith("classifier.3.")]
    unexpected = sorted(set(trainable) - set(features) - set(classifier))
    if unexpected or not features or set(classifier) != {"classifier.3.weight", "classifier.3.bias"}:
        raise RuntimeError(f"Configuración entrenable inesperada: {unexpected}")
    return trainable, features, classifier


def evaluate(
    model: nn.Module,
    loader: DataLoader,
    rows: list[dict[str, str]],
    classes: list[str],
    device: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    model.eval()
    truth: list[int] = []
    predicted: list[int] = []
    with torch.inference_mode():
        for images, targets in loader:
            outputs = model(images.to(device))
            truth.extend(int(value) for value in targets.tolist())
            predicted.extend(int(value) for value in outputs.argmax(dim=1).cpu().tolist())
    if len(truth) != len(rows):
        raise RuntimeError("La evaluación no coincide con las filas de VAL")
    indexes = list(range(len(classes)))
    precision, recall, class_f1, support = precision_recall_fscore_support(
        truth, predicted, labels=indexes, zero_division=0
    )
    matrix = confusion_matrix(truth, predicted, labels=indexes).tolist()
    metrics = {
        "split": "val",
        "images": len(truth),
        "macro_f1": float(f1_score(truth, predicted, labels=indexes, average="macro", zero_division=0)),
        "accuracy": float(accuracy_score(truth, predicted)),
        "classes": classes,
        "display_labels": [DISPLAY_NAMES[category] for category in classes],
        "per_class": {
            category: {
                "precision": float(precision[index]),
                "recall": float(recall[index]),
                "f1": float(class_f1[index]),
                "support": int(support[index]),
            }
            for index, category in enumerate(classes)
        },
        "confusion_matrix_rows_true_columns_predicted": matrix,
    }
    predictions = [
        {
            "path": row["path"],
            "true_class": classes[truth[index]],
            "predicted_class": classes[predicted[index]],
            "correct": truth[index] == predicted[index],
        }
        for index, row in enumerate(rows)
    ]
    return metrics, predictions


def write_confusion(path: Path, metrics: dict[str, Any]) -> None:
    labels = metrics["display_labels"]
    matrix = metrics["confusion_matrix_rows_true_columns_predicted"]
    rows = [
        {"true_label": label, **{f"pred_{labels[index]}": value for index, value in enumerate(matrix[row_index])}}
        for row_index, label in enumerate(labels)
    ]
    write_csv(path, rows, ["true_label", *[f"pred_{label}" for label in labels]])


def run_one(
    experiment_dir: Path,
    branch: str,
    indexes: tuple[int, ...],
    seed: int,
    train_rows: list[dict[str, str]],
    val_rows: list[dict[str, str]],
    source_hash: str,
    manifest_hash: str,
) -> dict[str, Any]:
    run_dir = experiment_dir / branch / f"seed_{seed}"
    run_dir.mkdir(parents=True, exist_ok=False)
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.use_deterministic_algorithms(True)

    model, metadata = load_checkpoint(SOURCE_CHECKPOINT)
    if metadata["model"] != "mobilenet" or metadata["manifest_sha256"] != manifest_hash:
        raise RuntimeError("El checkpoint inicial no es compatible con el manifiesto")
    classes = metadata["classes"]
    if classes != list(DISPLAY_NAMES):
        raise RuntimeError(f"Orden de clases inesperado: {classes}")

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = model.to(device)
    val_loader = DataLoader(
        Leaves(val_rows, classes, training=False),
        batch_size=BATCH_SIZE,
        shuffle=False,
        num_workers=0,
    )
    initial_metrics, _ = evaluate(model, val_loader, val_rows, classes, device)
    if abs(initial_metrics["macro_f1"] - float(metadata["val_macro_f1"])) > 1e-12:
        raise RuntimeError("El checkpoint inicial no reproduce su F1 macro de VAL")
    write_json(run_dir / "initial_validation_metrics.json", initial_metrics)

    trainable, feature_names, classifier_names = configure_trainable(model, indexes)
    named = dict(model.named_parameters())
    feature_parameters = [named[name] for name in feature_names]
    classifier_parameters = [named[name] for name in classifier_names]
    optimizer = torch.optim.Adam(
        [
            {"params": feature_parameters, "lr": FEATURE_LR, "name": "features"},
            {"params": classifier_parameters, "lr": CLASSIFIER_LR, "name": "classifier_last"},
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
    if not all((optimizer_check["all_trainable_parameters_in_optimizer"], optimizer_check["no_frozen_parameters_in_optimizer"])):
        raise RuntimeError("El optimizador no coincide con los parámetros entrenables")
    write_json(run_dir / "optimizer_check.json", optimizer_check)

    counts = np.array([sum(row["label"] == category for row in train_rows) for category in classes])
    class_weights = len(train_rows) / (len(classes) * counts)
    criterion = nn.CrossEntropyLoss(
        weight=torch.tensor(class_weights, dtype=torch.float32, device=device)
    )
    train_loader = DataLoader(
        Leaves(train_rows, classes, training=True),
        batch_size=BATCH_SIZE,
        shuffle=True,
        num_workers=0,
    )

    bn_before = batch_norm_state(model)
    conv_names = {
        f"{module_name}.{parameter_name}"
        for module_name, module in model.named_modules()
        if isinstance(module, nn.Conv2d)
        for parameter_name, _ in module.named_parameters(recurse=False)
    }
    trainable_conv_names = sorted(conv_names & set(trainable))
    total_parameters = sum(parameter.numel() for parameter in model.parameters())
    configuration = {
        "status": "running",
        "branch": branch,
        "seed": seed,
        "source_checkpoint": relative(SOURCE_CHECKPOINT),
        "source_checkpoint_sha256": source_hash,
        "manifest_sha256": manifest_hash,
        "test_used": False,
        "train_images": len(train_rows),
        "validation_images": len(val_rows),
        "unfrozen_feature_module_indexes": list(indexes),
        "trainable_parameter_names": trainable,
        "trainable_parameters": sum(named[name].numel() for name in trainable),
        "total_parameters": total_parameters,
        "trainable_fraction": sum(named[name].numel() for name in trainable) / total_parameters,
        "optimizer": "Adam",
        "learning_rates": {"features": FEATURE_LR, "classifier_last": CLASSIFIER_LR},
        "batch_size": BATCH_SIZE,
        "maximum_epochs": MAX_EPOCHS,
        "early_stopping_patience": PATIENCE,
        "selection_metric": "validation macro F1",
        "initial_checkpoint_is_candidate": True,
        "batch_norm_running_statistics_frozen": True,
        "batch_norm_affine_parameters_in_unfrozen_modules_trainable": True,
        "loss": "weighted cross entropy; class weights calculated only from train",
        "class_weights": {category: float(class_weights[index]) for index, category in enumerate(classes)},
        "preprocessing_source": "src/common.py::Leaves/transform",
        "preprocessing": {
            "orientation": "EXIF transpose",
            "color": "RGB",
            "resize": [224, 224],
            "interpolation": "torchvision Resize default: bilinear",
            "tensor": "ToTensor",
            "normalization_mean": [0.485, 0.456, 0.406],
            "normalization_std": [0.229, 0.224, 0.225],
        },
        "training_augmentation_order": [
            "Resize((224, 224))",
            "RandomHorizontalFlip()",
            "RandomRotation(15)",
            "ToTensor()",
            "Normalize(ImageNet)",
        ],
        "device": device,
        "deterministic_algorithms": True,
    }
    write_json(run_dir / "configuration.json", configuration)

    best_score = initial_metrics["macro_f1"]
    best_epoch = 0
    best_state = state_dict_cpu(model)
    history: list[dict[str, Any]] = [
        {
            "candidate_epoch": 0,
            "train_loss": None,
            "val_macro_f1": best_score,
            "improved_over_best": False,
            "consecutive_epochs_without_improvement": 0,
        }
    ]
    write_json(run_dir / "history.json", history)
    without_improvement = 0
    gradient_check: dict[str, Any] | None = None
    started = time.perf_counter()

    for epoch in range(1, MAX_EPOCHS + 1):
        model.train()
        freeze_batch_norm_statistics(model)
        loss_sum = 0.0
        for batch_index, (images, targets) in enumerate(train_loader):
            images = images.to(device)
            targets = targets.to(device)
            optimizer.zero_grad()
            loss = criterion(model(images), targets)
            loss.backward()
            if gradient_check is None:
                records = {
                    name: {
                        "gradient_present": parameter.grad is not None,
                        "gradient_norm": float(parameter.grad.detach().norm().cpu()) if parameter.grad is not None else None,
                    }
                    for name, parameter in named.items()
                    if parameter.requires_grad
                }
                gradient_check = {
                    "checked_epoch": epoch,
                    "checked_batch": batch_index + 1,
                    "all_trainable_parameters_have_gradients": all(
                        record["gradient_present"] for record in records.values()
                    ),
                    "all_unfrozen_convolution_parameters_have_nonzero_gradients": all(
                        records[name]["gradient_present"] and records[name]["gradient_norm"] > 0
                        for name in trainable_conv_names
                    ),
                    "unfrozen_convolution_parameter_names": trainable_conv_names,
                    "parameters": records,
                }
                if not all(
                    (
                        gradient_check["all_trainable_parameters_have_gradients"],
                        gradient_check["all_unfrozen_convolution_parameters_have_nonzero_gradients"],
                    )
                ):
                    raise RuntimeError("Falló la comprobación de gradientes")
                write_json(run_dir / "gradient_check.json", gradient_check)
            optimizer.step()
            loss_sum += float(loss.item()) * len(targets)

        validation, _ = evaluate(model, val_loader, val_rows, classes, device)
        improved = validation["macro_f1"] > best_score
        if improved:
            best_score = validation["macro_f1"]
            best_epoch = epoch
            best_state = state_dict_cpu(model)
            without_improvement = 0
        else:
            without_improvement += 1
        record = {
            "candidate_epoch": epoch,
            "train_loss": loss_sum / len(train_rows),
            "val_macro_f1": validation["macro_f1"],
            "improved_over_best": improved,
            "consecutive_epochs_without_improvement": without_improvement,
        }
        history.append(record)
        write_json(run_dir / "history.json", history)
        print(json.dumps({"branch": branch, "seed": seed, **record}, ensure_ascii=False), flush=True)
        if without_improvement >= PATIENCE:
            break

    duration = time.perf_counter() - started
    bn_after = batch_norm_state(model)
    bn_check = {
        "all_running_statistics_unchanged": all(
            torch.equal(bn_before[name][field], bn_after[name][field])
            for name in bn_before
            for field in bn_before[name]
        ),
        "module_count": len(bn_before),
    }
    if not bn_check["all_running_statistics_unchanged"]:
        raise RuntimeError("Las estadísticas BatchNorm cambiaron")
    write_json(run_dir / "batch_norm_check.json", bn_check)

    checkpoint = {
        "state_dict": best_state,
        "classes": classes,
        "model": "mobilenet",
        "val_macro_f1": best_score,
        "manifest_sha256": manifest_hash,
        "seed": seed,
        "epochs": len(history) - 1,
        "selected_candidate_epoch": best_epoch,
        "source_checkpoint_sha256": source_hash,
        "trainable_parameter_names": trainable,
        "fine_tuning": {
            "experiment": "depth",
            "branch": branch,
            "unfrozen_feature_module_indexes": list(indexes),
            "feature_learning_rate": FEATURE_LR,
            "classifier_learning_rate": CLASSIFIER_LR,
            "batch_norm_running_statistics_frozen": True,
            "early_stopping_patience": PATIENCE,
        },
    }
    torch.save(checkpoint, run_dir / "best_checkpoint.pt")
    model.load_state_dict(best_state)
    selected_metrics, predictions = evaluate(model, val_loader, val_rows, classes, device)
    selected_metrics.update(
        {
            "branch": branch,
            "seed": seed,
            "selected_candidate_epoch": best_epoch,
            "checkpoint": relative(run_dir / "best_checkpoint.pt"),
            "checkpoint_sha256": digest(run_dir / "best_checkpoint.pt"),
        }
    )
    write_json(run_dir / "validation_metrics.json", selected_metrics)
    write_confusion(run_dir / "validation_confusion_matrix.csv", selected_metrics)
    write_csv(
        run_dir / "validation_predictions.csv",
        predictions,
        ["path", "true_class", "predicted_class", "correct"],
    )

    summary = {
        "status": "complete",
        "branch": branch,
        "seed": seed,
        "selected_candidate_epoch": best_epoch,
        "epochs_run": len(history) - 1,
        "stopped_early": len(history) - 1 < MAX_EPOCHS,
        "duration_seconds": duration,
        "initial_validation_macro_f1": initial_metrics["macro_f1"],
        "selected_validation_macro_f1": selected_metrics["macro_f1"],
        "selected_checkpoint_sha256": selected_metrics["checkpoint_sha256"],
        "trainable_parameters": configuration["trainable_parameters"],
    }
    write_json(run_dir / "summary.json", summary)
    configuration.update(
        {
            "status": "complete",
            "epochs_run": summary["epochs_run"],
            "selected_candidate_epoch": best_epoch,
            "selected_validation_macro_f1": selected_metrics["macro_f1"],
            "duration_seconds": duration,
        }
    )
    write_json(run_dir / "configuration.json", configuration)
    return {"summary": summary, "metrics": selected_metrics}


def sample_stats(values: list[float]) -> dict[str, float]:
    return {
        "mean": statistics.mean(values),
        "sample_standard_deviation": statistics.stdev(values),
        "min": min(values),
        "max": max(values),
    }


def aggregate(experiment_dir: Path, results: list[dict[str, Any]]) -> dict[str, Any]:
    by_key = {(entry["summary"]["branch"], entry["summary"]["seed"]): entry for entry in results}
    classes = next(iter(by_key.values()))["metrics"]["classes"]
    branches: dict[str, Any] = {}
    for branch in BRANCHES:
        entries = [by_key[(branch, seed)] for seed in SEEDS]
        branches[branch] = {
            "macro_f1": sample_stats([entry["metrics"]["macro_f1"] for entry in entries]),
            "accuracy_descriptive": sample_stats([entry["metrics"]["accuracy"] for entry in entries]),
            "duration_seconds": sample_stats([entry["summary"]["duration_seconds"] for entry in entries]),
            "per_class": {
                category: {
                    metric: sample_stats(
                        [entry["metrics"]["per_class"][category][metric] for entry in entries]
                    )
                    for metric in ("precision", "recall", "f1")
                }
                for category in classes
            },
        }

    paired: list[dict[str, Any]] = []
    for seed in SEEDS:
        control = by_key[("control", seed)]["metrics"]
        candidate = by_key[("candidate", seed)]["metrics"]
        paired.append(
            {
                "seed": seed,
                "control_macro_f1": control["macro_f1"],
                "candidate_macro_f1": candidate["macro_f1"],
                "candidate_minus_control_macro_f1": candidate["macro_f1"] - control["macro_f1"],
            }
        )

    mean_gain = branches["candidate"]["macro_f1"]["mean"] - branches["control"]["macro_f1"]["mean"]
    positive_pairs = sum(row["candidate_minus_control_macro_f1"] > 0 for row in paired)
    recall_deltas = {
        category: (
            branches["candidate"]["per_class"][category]["recall"]["mean"]
            - branches["control"]["per_class"][category]["recall"]["mean"]
        )
        for category in classes
    }
    criteria = {
        "mean_macro_f1_gain_at_least_0_010": mean_gain >= MIN_MEAN_MACRO_F1_GAIN,
        "positive_macro_f1_delta_in_at_least_two_seeds": positive_pairs >= 2,
        "no_mean_class_recall_drop_greater_than_0_020": all(
            delta >= -MAX_MEAN_CLASS_RECALL_DROP for delta in recall_deltas.values()
        ),
    }
    payload = {
        "status": "complete",
        "test_used": False,
        "seeds": list(SEEDS),
        "branches": branches,
        "paired_macro_f1": paired,
        "mean_candidate_minus_control_macro_f1": mean_gain,
        "mean_candidate_minus_control_recall_by_class": recall_deltas,
        "acceptance_criteria": criteria,
        "candidate_meets_all_operational_criteria": all(criteria.values()),
        "caution": "Tres semillas sobre VAL reutilizado no demuestran generalización.",
    }
    write_json(experiment_dir / "comparison.json", payload)

    rows: list[dict[str, Any]] = []
    for entry in results:
        metrics = entry["metrics"]
        row: dict[str, Any] = {
            "branch": entry["summary"]["branch"],
            "seed": entry["summary"]["seed"],
            "selected_epoch": entry["summary"]["selected_candidate_epoch"],
            "epochs_run": entry["summary"]["epochs_run"],
            "duration_seconds": entry["summary"]["duration_seconds"],
            "macro_f1": metrics["macro_f1"],
            "accuracy_descriptive": metrics["accuracy"],
        }
        for category in classes:
            for metric in ("precision", "recall", "f1"):
                row[f"{category}_{metric}"] = metrics["per_class"][category][metric]
        rows.append(row)
    write_csv(experiment_dir / "runs.csv", rows, list(rows[0].keys()))
    write_csv(
        experiment_dir / "paired_macro_f1.csv",
        paired,
        ["seed", "control_macro_f1", "candidate_macro_f1", "candidate_minus_control_macro_f1"],
    )
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--experiment-dir", type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.experiment_dir:
        experiment_dir = args.experiment_dir if args.experiment_dir.is_absolute() else ROOT / args.experiment_dir
        experiment_dir.mkdir(parents=True, exist_ok=False)
    else:
        experiment_dir = ROOT / "experiments" / f"mobilenet_depth_{datetime.now():%Y%m%d-%H%M%S}"
        experiment_dir.mkdir(parents=True, exist_ok=False)
    print(f"EXPERIMENT_DIR={relative(experiment_dir)}", flush=True)

    manifest = ROOT / "data" / "processed" / "manifest.csv"
    source_hash = digest(SOURCE_CHECKPOINT)
    manifest_hash = digest(manifest)
    if source_hash != EXPECTED_SOURCE_SHA256:
        raise RuntimeError(f"SHA-256 inicial inesperado: {source_hash}")
    if manifest_hash != EXPECTED_MANIFEST_SHA256:
        raise RuntimeError(f"SHA-256 del manifiesto inesperado: {manifest_hash}")
    before = snapshot(ACTIVE_PATHS)
    write_json(experiment_dir / "active_files_before.json", before)
    shutil.copy2(ROOT / "reports" / "MOBILENET_DEPTH_EXPERIMENT_PROTOCOL.md", experiment_dir / "PROTOCOL.md")

    train_rows, val_rows, skipped = read_train_val()
    if len(train_rows) != 880 or len(val_rows) != 301:
        raise RuntimeError(f"Conteos inesperados TRAIN/VAL: {len(train_rows)}/{len(val_rows)}")
    preflight = {
        "status": "complete_before_training",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "source_checkpoint": relative(SOURCE_CHECKPOINT),
        "source_checkpoint_sha256": source_hash,
        "manifest_sha256": manifest_hash,
        "train_images": len(train_rows),
        "validation_images": len(val_rows),
        "test_images_opened": 0,
        "test_rows_skipped_without_retaining_path_label_or_hash": skipped.get("test", 0),
        "seeds": list(SEEDS),
        "branches": {name: list(indexes) for name, indexes in BRANCHES.items()},
        "maximum_epochs_per_run": MAX_EPOCHS,
        "early_stopping_patience": PATIENCE,
        "selection_metric": "validation macro F1",
        "acceptance": {
            "minimum_mean_macro_f1_gain": MIN_MEAN_MACRO_F1_GAIN,
            "minimum_positive_seed_pairs": 2,
            "maximum_mean_recall_drop_per_class": MAX_MEAN_CLASS_RECALL_DROP,
        },
    }
    write_json(experiment_dir / "preflight.json", preflight)

    results: list[dict[str, Any]] = []
    for seed in SEEDS:
        for branch, indexes in BRANCHES.items():
            results.append(
                run_one(
                    experiment_dir,
                    branch,
                    indexes,
                    seed,
                    train_rows,
                    val_rows,
                    source_hash,
                    manifest_hash,
                )
            )
    comparison = aggregate(experiment_dir, results)
    after = snapshot(ACTIVE_PATHS)
    write_json(experiment_dir / "active_files_after.json", after)
    if before != after:
        raise RuntimeError("Cambió un archivo activo durante el experimento")
    write_json(
        experiment_dir / "experiment_summary.json",
        {
            "status": "complete",
            "experiment_dir": relative(experiment_dir),
            "runs": len(results),
            "test_used": False,
            "active_files_unchanged": True,
            "candidate_meets_all_operational_criteria": comparison["candidate_meets_all_operational_criteria"],
        },
    )
    print(json.dumps(comparison, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
