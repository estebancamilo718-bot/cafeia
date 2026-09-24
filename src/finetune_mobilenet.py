"""Ajuste fino controlado de MobileNet usando solo train y val.

Parte de un checkpoint existente, conserva BatchNorm en modo evaluación y
escribe siempre en una carpeta de experimento nueva. Nunca accede a test ni
modifica el checkpoint activo de models/.
"""

import argparse
import hashlib
import json
import random
import shutil
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import torch
from sklearn.metrics import confusion_matrix, f1_score, precision_recall_fscore_support
from torch import nn
from torch.utils.data import DataLoader

from src.common import ROOT, Leaves, load_checkpoint, read_rows


SEED = 42
FEATURE_LEARNING_RATE = 1e-5
CLASSIFIER_LEARNING_RATE = 1e-4
PATIENCE = 4
MAX_EPOCHS = 15
DISPLAY_NAMES = {
    "coffee___healthy": "Hoja sana",
    "coffee___red_spider_mite": "Ácaro rojo",
    "coffee___rust": "Roya",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def new_experiment_dir() -> Path:
    base = ROOT / "experiments" / f"mobilenet_finetune_{datetime.now():%Y%m%d-%H%M%S}"
    candidate = base
    suffix = 1
    while candidate.exists():
        candidate = Path(f"{base}-{suffix}")
        suffix += 1
    candidate.mkdir(parents=True)
    return candidate


def freeze_batch_norm_statistics(model: nn.Module) -> None:
    for module in model.modules():
        if isinstance(module, nn.modules.batchnorm._BatchNorm):
            module.eval()


def batch_norm_state(model: nn.Module) -> dict[str, dict[str, torch.Tensor]]:
    state = {}
    for name, module in model.named_modules():
        if isinstance(module, nn.modules.batchnorm._BatchNorm):
            state[name] = {
                "running_mean": module.running_mean.detach().cpu().clone(),
                "running_var": module.running_var.detach().cpu().clone(),
                "num_batches_tracked": module.num_batches_tracked.detach().cpu().clone(),
            }
    return state


def state_dict_cpu(model: nn.Module) -> dict[str, torch.Tensor]:
    return {name: value.detach().cpu().clone() for name, value in model.state_dict().items()}


def evaluate(model: nn.Module, loader: DataLoader, device: str, class_count: int) -> dict:
    model.eval()
    truth: list[int] = []
    predicted: list[int] = []
    with torch.inference_mode():
        for images, targets in loader:
            outputs = model(images.to(device))
            truth.extend(targets.tolist())
            predicted.extend(outputs.argmax(dim=1).cpu().tolist())
    indexes = list(range(class_count))
    precision, recall, f1, support = precision_recall_fscore_support(
        truth, predicted, labels=indexes, zero_division=0
    )
    return {
        "macro_f1": float(f1_score(truth, predicted, labels=indexes, average="macro", zero_division=0)),
        "precision": [float(value) for value in precision],
        "recall": [float(value) for value in recall],
        "f1": [float(value) for value in f1],
        "support": [int(value) for value in support],
        "confusion_matrix_rows_true_columns_predicted": confusion_matrix(
            truth, predicted, labels=indexes
        ).tolist(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Un único ajuste fino controlado de MobileNet.")
    parser.add_argument("--checkpoint", type=Path, default=Path("models/mobilenet.pt"))
    parser.add_argument("--max-epochs", type=int, default=MAX_EPOCHS)
    parser.add_argument("--patience", type=int, default=PATIENCE)
    parser.add_argument("--batch-size", type=int, default=16)
    args = parser.parse_args()
    if not 1 <= args.max_epochs <= MAX_EPOCHS:
        parser.error(f"max-epochs debe estar entre 1 y {MAX_EPOCHS}")
    if args.patience != PATIENCE:
        parser.error(f"Este experimento controlado exige patience={PATIENCE}")
    if args.batch_size < 1:
        parser.error("batch-size debe ser positivo")

    source_checkpoint = args.checkpoint if args.checkpoint.is_absolute() else ROOT / args.checkpoint
    if not source_checkpoint.is_file():
        raise FileNotFoundError(f"No existe el checkpoint inicial: {source_checkpoint}")
    source_hash = sha256(source_checkpoint)
    manifest_path = ROOT / "data" / "processed" / "manifest.csv"
    manifest_hash = sha256(manifest_path)

    random.seed(SEED)
    np.random.seed(SEED)
    torch.manual_seed(SEED)

    rows = read_rows()
    train_rows = [row for row in rows if row["split"] == "train"]
    val_rows = [row for row in rows if row["split"] == "val"]
    if not train_rows or not val_rows:
        raise ValueError("Faltan filas de train o val en el manifiesto")

    model, source_metadata = load_checkpoint(source_checkpoint)
    if source_metadata["model"] != "mobilenet":
        raise ValueError("El checkpoint inicial no es MobileNet")
    if source_metadata["seed"] != SEED:
        raise ValueError(f"El checkpoint no usa la semilla {SEED}")
    if source_metadata["manifest_sha256"] != manifest_hash:
        raise ValueError("El checkpoint inicial no corresponde al manifiesto actual")
    classes = source_metadata["classes"]
    if set(classes) != set(DISPLAY_NAMES):
        raise ValueError(f"Clases inesperadas: {classes}")

    experiment_dir = new_experiment_dir()
    print(f"EXPERIMENT_DIR={experiment_dir.relative_to(ROOT)}", flush=True)
    initial_copy = experiment_dir / "candidate_initial_epoch0.pt"
    shutil.copy2(source_checkpoint, initial_copy)

    train_loader = DataLoader(
        Leaves(train_rows, classes, training=True),
        batch_size=args.batch_size,
        shuffle=True,
        num_workers=0,
    )
    val_loader = DataLoader(
        Leaves(val_rows, classes, training=False),
        batch_size=args.batch_size,
        shuffle=False,
        num_workers=0,
    )
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = model.to(device)

    initial_metrics = evaluate(model, val_loader, device, len(classes))
    expected_initial = float(source_metadata["val_macro_f1"])
    if abs(initial_metrics["macro_f1"] - expected_initial) > 1e-12:
        raise RuntimeError(
            f"La validación inicial ({initial_metrics['macro_f1']}) no reproduce el checkpoint ({expected_initial})"
        )
    initial_metrics["classes"] = classes
    initial_metrics["display_labels"] = [DISPLAY_NAMES[category] for category in classes]
    initial_metrics["candidate_epoch"] = 0
    initial_metrics["checkpoint_sha256"] = source_hash
    write_json(experiment_dir / "initial_validation_metrics.json", initial_metrics)

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
    unexpected = sorted(set(trainable_names) - set(feature_names) - set(classifier_names))
    if unexpected or not feature_names or set(classifier_names) != {"classifier.3.weight", "classifier.3.bias"}:
        raise RuntimeError(f"Configuración entrenable inesperada: {unexpected}")

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
        "no_frozen_parameters_in_optimizer": all(parameter.requires_grad for group in optimizer.param_groups for parameter in group["params"]),
        "groups": [
            {
                "name": group["name"],
                "learning_rate": group["lr"],
                "parameter_count": sum(parameter.numel() for parameter in group["params"]),
                "parameter_names": feature_names if group["name"] == "features_last_three" else classifier_names,
            }
            for group in optimizer.param_groups
        ],
    }
    if not optimizer_check["all_trainable_parameters_in_optimizer"] or not optimizer_check["no_frozen_parameters_in_optimizer"]:
        raise RuntimeError("El optimizador no coincide exactamente con los parámetros descongelados")
    write_json(experiment_dir / "optimizer_check.json", optimizer_check)

    counts = np.array([sum(row["label"] == category for row in train_rows) for category in classes])
    class_weights = len(train_rows) / (len(classes) * counts)
    criterion = nn.CrossEntropyLoss(
        weight=torch.tensor(class_weights, dtype=torch.float32, device=device)
    )

    bn_before = batch_norm_state(model)
    conv_parameter_names: set[str] = set()
    for module_name, module in model.named_modules():
        if isinstance(module, nn.Conv2d):
            for parameter_name, _ in module.named_parameters(recurse=False):
                conv_parameter_names.add(f"{module_name}.{parameter_name}")
    trainable_conv_names = sorted(conv_parameter_names & set(trainable_names))

    started = time.perf_counter()
    best_score = initial_metrics["macro_f1"]
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
    epochs_without_improvement = 0
    gradient_check = None

    configuration = {
        "status": "running",
        "model": "mobilenet",
        "architecture": "MobileNetV3 Small",
        "source_checkpoint": str(source_checkpoint.relative_to(ROOT)) if source_checkpoint.is_relative_to(ROOT) else str(source_checkpoint),
        "source_checkpoint_sha256": source_hash,
        "source_validation_macro_f1": expected_initial,
        "seed": SEED,
        "manifest_sha256": manifest_hash,
        "train_images": len(train_rows),
        "validation_images": len(val_rows),
        "test_used": False,
        "batch_size": args.batch_size,
        "maximum_epochs": args.max_epochs,
        "early_stopping_patience": args.patience,
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
        "preprocessing": {
            "orientation": "EXIF transpose",
            "color": "RGB",
            "resize": [224, 224],
            "tensor": "ToTensor",
            "normalization_mean": [0.485, 0.456, 0.406],
            "normalization_std": [0.229, 0.224, 0.225],
        },
        "training_augmentation": ["RandomHorizontalFlip", "RandomRotation(15 degrees)"],
        "validation_augmentation": False,
        "device": device,
    }
    write_json(experiment_dir / "configuration.json", configuration)
    write_json(experiment_dir / "history.json", history)

    for epoch in range(1, args.max_epochs + 1):
        model.train()
        freeze_batch_norm_statistics(model)
        total_loss = 0.0
        for batch_index, (images, targets) in enumerate(train_loader):
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
                    "unfrozen_convolution_parameter_names": trainable_conv_names,
                    "parameters": gradient_records,
                }
                if not gradient_check["all_trainable_parameters_have_gradients"] or not gradient_check["all_unfrozen_convolution_parameters_have_nonzero_gradients"]:
                    raise RuntimeError("Falló la comprobación de gradientes de los parámetros descongelados")
                write_json(experiment_dir / "gradient_check.json", gradient_check)

            optimizer.step()
            total_loss += float(loss.item()) * len(targets)

        validation = evaluate(model, val_loader, device, len(classes))
        improved = validation["macro_f1"] > best_score
        if improved:
            best_score = validation["macro_f1"]
            best_epoch = epoch
            best_state = state_dict_cpu(model)
            epochs_without_improvement = 0
        else:
            epochs_without_improvement += 1
        record = {
            "candidate_epoch": epoch,
            "train_loss": total_loss / len(train_rows),
            "val_macro_f1": validation["macro_f1"],
            "improved_over_best": improved,
            "consecutive_epochs_without_improvement": epochs_without_improvement,
        }
        history.append(record)
        write_json(experiment_dir / "history.json", history)
        print(json.dumps(record, ensure_ascii=False), flush=True)
        if epochs_without_improvement >= args.patience:
            break

    duration_seconds = time.perf_counter() - started
    bn_after = batch_norm_state(model)
    bn_checks = {
        name: {
            key: bool(torch.equal(bn_before[name][key], bn_after[name][key]))
            for key in bn_before[name]
        }
        for name in bn_before
    }
    bn_check = {
        "all_running_statistics_unchanged": all(
            all(values.values()) for values in bn_checks.values()
        ),
        "batch_norm_modules": bn_checks,
    }
    if not bn_check["all_running_statistics_unchanged"]:
        raise RuntimeError("Las estadísticas BatchNorm cambiaron durante el ajuste fino")
    write_json(experiment_dir / "batch_norm_check.json", bn_check)

    best_checkpoint = {
        "state_dict": best_state,
        "classes": classes,
        "model": "mobilenet",
        "val_macro_f1": best_score,
        "manifest_sha256": manifest_hash,
        "seed": SEED,
        "epochs": len(history) - 1,
        "selected_candidate_epoch": best_epoch,
        "source_checkpoint_sha256": source_hash,
        "trainable_parameter_names": trainable_names,
        "fine_tuning": {
            "unfrozen_feature_module_indexes": feature_indexes,
            "feature_learning_rate": FEATURE_LEARNING_RATE,
            "classifier_learning_rate": CLASSIFIER_LEARNING_RATE,
            "batch_norm_running_statistics_frozen": True,
            "early_stopping_patience": args.patience,
        },
    }
    torch.save(best_checkpoint, experiment_dir / "best_checkpoint.pt")

    final_source_hash = sha256(source_checkpoint)
    if final_source_hash != source_hash:
        raise RuntimeError("El checkpoint activo cambió durante el experimento")
    summary = {
        "status": "complete",
        "selected_candidate_epoch": best_epoch,
        "initial_validation_macro_f1": initial_metrics["macro_f1"],
        "best_validation_macro_f1": best_score,
        "absolute_macro_f1_change": best_score - initial_metrics["macro_f1"],
        "epochs_run": len(history) - 1,
        "stopped_early": len(history) - 1 < args.max_epochs,
        "duration_seconds": duration_seconds,
        "active_checkpoint_unchanged": True,
        "active_checkpoint_sha256": final_source_hash,
        "selected_checkpoint": "best_checkpoint.pt",
        "initial_candidate_checkpoint": "candidate_initial_epoch0.pt",
    }
    write_json(experiment_dir / "summary.json", summary)
    configuration.update(
        {
            "status": "complete",
            "epochs_run": summary["epochs_run"],
            "selected_candidate_epoch": best_epoch,
            "best_validation_macro_f1": best_score,
            "duration_seconds": duration_seconds,
        }
    )
    write_json(experiment_dir / "configuration.json", configuration)
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
