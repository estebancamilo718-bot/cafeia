"""Comprobación E2E reproducible sobre una muestra fijada de VAL.

La selección se ejecuta en una fase separada y no carga el modelo. La fase
``run`` compara inferencia directa y la API HTTP sin convertir esta muestra
pequeña en una nueva evaluación global.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import torch
from PIL import Image, ImageOps

from src.common import ROOT, load_checkpoint, transform
from src.verify_api_flow import get_json, post_file, sha256_file


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
SELECTION_SEED = 42
SAMPLES_PER_CLASS = 5
UNCERTAINTY_THRESHOLD = 0.70
SCORE_ABSOLUTE_TOLERANCE = 1e-7
EXPECTED_CHECKPOINT_SHA256 = "4ab4e52fc3d417fe5fb126ff1e5b346f080c55ffa80232cffd5d6e6622e46c94"
EXPECTED_MANIFEST_SHA256 = "1ea21d6b2b480b830065c5d4d1d90f531234cc2aa244d7bb98c5873363866dab"

MANIFEST_PATH = ROOT / "data" / "processed" / "manifest.csv"
AUDIT_PATH = (
    ROOT
    / "provenance"
    / "rocole_mendeley_v2"
    / "evidence"
    / "train_val_annotation_comparison.csv"
)
DEFAULT_SELECTION_PATH = ROOT / "reports" / "val_e2e" / "selection.csv"
DEFAULT_SELECTION_METADATA_PATH = ROOT / "reports" / "val_e2e" / "selection_metadata.json"
DEFAULT_OUTPUT_DIR = ROOT / "reports" / "val_e2e"
DEFAULT_REPORT_PATH = ROOT / "reports" / "VAL_E2E_INTEGRATION.md"
DEFAULT_CHECKPOINT_PATH = ROOT / "models" / "mobilenet_finetuned_epoch6.pt"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def stable_key(*parts: str) -> str:
    material = "\x1f".join((str(SELECTION_SEED), *parts))
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def audit_rows_by_path() -> dict[str, dict[str, str]]:
    if not AUDIT_PATH.is_file():
        raise FileNotFoundError(f"No se encontró la evidencia auditada: {AUDIT_PATH}")
    rows = read_csv(AUDIT_PATH)
    by_path: dict[str, dict[str, str]] = {}
    for row in rows:
        local_path = row["local_path"]
        if local_path in by_path:
            raise RuntimeError(f"Ruta repetida en la evidencia auditada: {local_path}")
        by_path[local_path] = row
    return by_path


def validate_audit(manifest_row: dict[str, str], audit_row: dict[str, str]) -> None:
    expected = {
        "split": "val",
        "local_path": manifest_row["path"],
        "converted_local_class": manifest_row["label"],
        "local_class": manifest_row["label"],
        "relation_status": "derived_content_consistent",
        "label_match_after_conversion": "True",
        "annotation_row_count": "1",
    }
    mismatches = {
        key: {"expected": value, "found": audit_row.get(key)}
        for key, value in expected.items()
        if audit_row.get(key) != value
    }
    if mismatches:
        raise RuntimeError(
            f"La evidencia original no valida {manifest_row['path']}: {mismatches}"
        )


def deterministic_selection() -> list[dict[str, str]]:
    if sha256_file(MANIFEST_PATH) != EXPECTED_MANIFEST_SHA256:
        raise RuntimeError("El SHA256 del manifiesto no coincide con el protocolo fijado")

    # Solo se conservan filas VAL. La selección no abre imágenes ni carga el modelo.
    val_rows = [row for row in read_csv(MANIFEST_PATH) if row["split"] == "val"]
    by_class_group: dict[str, dict[str, list[dict[str, str]]]] = {
        category: defaultdict(list) for category in CLASS_ORDER
    }
    for row in val_rows:
        if row["label"] not in by_class_group:
            raise RuntimeError(f"Clase VAL inesperada: {row['label']}")
        by_class_group[row["label"]][row["group"]].append(row)

    audit_by_path = audit_rows_by_path()
    used_groups: set[str] = set()
    selected: list[dict[str, str]] = []
    for category in CLASS_ORDER:
        groups = by_class_group[category]
        ranked_groups = sorted(
            groups,
            key=lambda group: (stable_key("group", category, group), group),
        )
        class_count = 0
        for group in ranked_groups:
            if group in used_groups:
                continue
            ranked_files = sorted(
                groups[group],
                key=lambda row: (stable_key("file", category, row["path"]), row["path"]),
            )
            manifest_row = ranked_files[0]
            audit_row = audit_by_path.get(manifest_row["path"])
            if audit_row is None:
                raise RuntimeError(
                    f"No hay evidencia de anotación original para {manifest_row['path']}"
                )
            validate_audit(manifest_row, audit_row)
            image_path = ROOT / manifest_row["path"]
            if not image_path.is_file():
                raise FileNotFoundError(f"No se encontró la imagen VAL: {image_path}")
            if sha256_file(image_path) != manifest_row["sha256"]:
                raise RuntimeError(f"SHA256 local inesperado: {manifest_row['path']}")

            class_count += 1
            used_groups.add(group)
            selected.append(
                {
                    "selection_index": str(len(selected) + 1),
                    "class_selection_rank": str(class_count),
                    "path": manifest_row["path"],
                    "filename": Path(manifest_row["path"]).name,
                    "split": "val",
                    "label": category,
                    "label_display": DISPLAY_NAMES[category],
                    "group": group,
                    "local_sha256": manifest_row["sha256"],
                    "original_classification": audit_row["original_classification"],
                    "annotation_id": audit_row["annotation_id"],
                    "annotation_relation": audit_row["relation_status"],
                    "label_match_after_conversion": audit_row["label_match_after_conversion"],
                    "group_rank_key": stable_key("group", category, group),
                    "file_rank_key": stable_key("file", category, manifest_row["path"]),
                    "selection_criterion": (
                        "primera imagen por orden SHA256 estable del primer grupo VAL aún no "
                        "usado; semilla textual 42; sin predicciones"
                    ),
                }
            )
            if class_count == SAMPLES_PER_CLASS:
                break
        if class_count != SAMPLES_PER_CLASS:
            raise RuntimeError(
                f"No hay {SAMPLES_PER_CLASS} grupos distintos disponibles para {category}"
            )

    if len({row["group"] for row in selected}) != len(selected):
        raise RuntimeError("La selección no quedó separada por planta/grupo")
    return selected


SELECTION_FIELDS = [
    "selection_index",
    "class_selection_rank",
    "path",
    "filename",
    "split",
    "label",
    "label_display",
    "group",
    "local_sha256",
    "original_classification",
    "annotation_id",
    "annotation_relation",
    "label_match_after_conversion",
    "group_rank_key",
    "file_rank_key",
    "selection_criterion",
]


def select_command(selection_path: Path, metadata_path: Path) -> None:
    selected = deterministic_selection()
    serialized_rows = [dict(row) for row in selected]

    if selection_path.exists():
        existing = read_csv(selection_path)
        if existing != serialized_rows:
            raise RuntimeError(
                "La selección existente no coincide con la recomputada; no se sobrescribió"
            )
    else:
        write_csv(selection_path, serialized_rows, SELECTION_FIELDS)

    metadata = {
        "scope": "VAL only; no TEST images, annotations or predictions",
        "selection_before_prediction": True,
        "model_loaded_during_selection": False,
        "seed": SELECTION_SEED,
        "samples_per_class": SAMPLES_PER_CLASS,
        "class_order": CLASS_ORDER,
        "distinct_groups_across_entire_sample": True,
        "selection_algorithm": (
            "rank groups and paths by SHA256(seed=42, class, identifier); choose the first "
            "file from five unused groups per class"
        ),
        "manifest_path": str(MANIFEST_PATH.relative_to(ROOT)).replace("\\", "/"),
        "manifest_sha256": sha256_file(MANIFEST_PATH),
        "annotation_evidence_path": str(AUDIT_PATH.relative_to(ROOT)).replace("\\", "/"),
        "selection_path": str(selection_path.relative_to(ROOT)).replace("\\", "/"),
        "selection_sha256": sha256_file(selection_path),
        "selected_files": len(selected),
        "selected_groups": len({row["group"] for row in selected}),
    }
    if metadata_path.exists():
        existing_metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        if existing_metadata != metadata:
            raise RuntimeError(
                "Los metadatos existentes no coinciden con la selección; no se sobrescribieron"
            )
    else:
        write_json(metadata_path, metadata)

    print(json.dumps(metadata, ensure_ascii=False, indent=2))


def validate_fixed_selection(selection_path: Path) -> list[dict[str, str]]:
    if not selection_path.is_file():
        raise FileNotFoundError(
            f"Primero fija la selección con el subcomando select: {selection_path}"
        )
    rows = read_csv(selection_path)
    if len(rows) != len(CLASS_ORDER) * SAMPLES_PER_CLASS:
        raise RuntimeError("La selección fijada no contiene exactamente 15 filas")

    manifest_by_path = {
        row["path"]: row for row in read_csv(MANIFEST_PATH) if row["split"] == "val"
    }
    audit_by_path = audit_rows_by_path()
    counts = {category: 0 for category in CLASS_ORDER}
    groups: set[str] = set()
    for row in rows:
        if row["split"] != "val" or row["label"] not in counts:
            raise RuntimeError(f"Fila fuera del alcance VAL fijado: {row}")
        manifest_row = manifest_by_path.get(row["path"])
        if manifest_row is None:
            raise RuntimeError(f"La ruta ya no está en VAL: {row['path']}")
        for field in ("label", "group", "sha256"):
            selection_field = "local_sha256" if field == "sha256" else field
            if row[selection_field] != manifest_row[field]:
                raise RuntimeError(f"La selección difiere del manifiesto: {row['path']}")
        audit_row = audit_by_path.get(row["path"])
        if audit_row is None:
            raise RuntimeError(f"Falta evidencia original: {row['path']}")
        validate_audit(manifest_row, audit_row)
        if row["original_classification"] != audit_row["original_classification"]:
            raise RuntimeError(f"Cambió la anotación original: {row['path']}")
        if row["group"] in groups:
            raise RuntimeError(f"Grupo repetido en la muestra: {row['group']}")
        groups.add(row["group"])
        counts[row["label"]] += 1
        image_path = ROOT / row["path"]
        if sha256_file(image_path) != row["local_sha256"]:
            raise RuntimeError(f"Cambió el archivo seleccionado: {row['path']}")
    if any(count != SAMPLES_PER_CLASS for count in counts.values()):
        raise RuntimeError(f"Distribución de clases inesperada: {counts}")
    return rows


def direct_scores(model: torch.nn.Module, image_path: Path) -> list[float]:
    with Image.open(image_path) as image:
        rgb = ImageOps.exif_transpose(image).convert("RGB")
        tensor = transform(training=False)(rgb).unsqueeze(0)
    with torch.inference_mode():
        return torch.softmax(model(tensor), dim=1)[0].tolist()


def score_map(scores: list[dict[str, Any]]) -> dict[str, float]:
    return {str(item["category"]): float(item["score"]) for item in scores}


def markdown_report(payload: dict[str, Any]) -> str:
    selection_rows = []
    result_rows = []
    for row in payload["results"]:
        selection_rows.append(
            "| `{filename}` | `{group}` | {label_display} | `{original}` | `{annotation}` |".format(
                filename=row["filename"],
                group=row["group"],
                label_display=row["true_label_display"],
                original=row["original_classification"],
                annotation=row["annotation_id"],
            )
        )
        result_rows.append(
            "| `{filename}` | {true_label} | {predicted} | {healthy:.6f} | {mite:.6f} | "
            "{rust:.6f} | {correct} | {uncertain} | {agreement} |".format(
                filename=row["filename"],
                true_label=row["true_label_display"],
                predicted=row["predicted_label_display"],
                healthy=row["api_scores"]["coffee___healthy"],
                mite=row["api_scores"]["coffee___red_spider_mite"],
                rust=row["api_scores"]["coffee___rust"],
                correct="Acierto" if row["classification_correct"] else "Error",
                uncertain="Sí" if row["is_uncertain"] else "No",
                agreement="Sí" if row["integration_agreement"] else "No",
            )
        )

    incorrect = [row for row in payload["results"] if not row["classification_correct"]]
    uncertain = [row for row in payload["results"] if row["is_uncertain"]]
    incorrect_lines = (
        "\n".join(
            f"- `{row['path']}`: etiqueta {row['true_label_display']}; predicción "
            f"{row['predicted_label_display']}."
            for row in incorrect
        )
        or "- No aparecieron errores en esta muestra fijada."
    )
    uncertain_lines = (
        "\n".join(
            f"- `{row['path']}`: clase más probable {row['predicted_label_display']}, "
            f"puntuación {row['top_score']:.6f}."
            for row in uncertain
        )
        or "- No aparecieron resultados por debajo de 0.70 en esta muestra fijada."
    )

    browser_rows = "\n".join(
        f"- {item['purpose']}: `{item['path']}`"
        for item in payload["browser_candidates"]
    )

    return f"""# Comprobación E2E con fotografías reales de VAL

**Fecha:** 2026-09-28

**Alcance:** comprobación de integración sobre 15 fotografías de VAL; no es una evaluación independiente ni una nueva estimación de precisión global. No se abrieron imágenes, anotaciones ni predicciones de TEST.

## Selección fijada antes de predecir

El subcomando `select` no carga el checkpoint. Con semilla textual 42 ordena grupos y archivos mediante SHA256, elige cinco grupos distintos por clase y una imagen por grupo. Los 15 grupos también son distintos entre clases. El archivo fijado es `reports/val_e2e/selection.csv`, SHA256 `{payload['selection_sha256']}`.

Cada fila se contrastó con la comparación de anotaciones originales ya auditada: relación `derived_content_consistent`, una sola anotación y coincidencia de etiqueta tras convertir `rust_level_1` a `rust_level_4` en la clase local única roya.

| Archivo | Planta/grupo | Etiqueta local | Anotación original | ID de anotación |
|---|---|---|---|---|
{chr(10).join(selection_rows)}

## Contrato comparado

- Checkpoint: `models/mobilenet_finetuned_epoch6.pt`, SHA256 `{payload['checkpoint_sha256']}`.
- Orden: `coffee___healthy`, `coffee___red_spider_mite`, `coffee___rust`.
- Preprocesamiento en ambas rutas: orientación EXIF, RGB, `Resize((224, 224))`, `ToTensor` y normalización ImageNet.
- Umbral conservado: `0.70`.
- API local comprobada: `{payload['api_base_url']}`; `/health` informó el mismo hash y orden de clases.
- Tolerancia absoluta por puntuación: `{payload['score_absolute_tolerance']:.0e}`. Es del orden de una unidad de último lugar de float32 cerca de 1 y cubre una diferencia numérica mínima entre procesos o serialización, pero sigue siendo suficientemente estricta para detectar un cambio material de pesos, orden o transformación.

## Resultados completos

Las puntuaciones son salidas softmax y no probabilidades calibradas de acierto.

| Archivo | Etiqueta real | Clase predicha | Sana | Ácaro rojo | Roya | Clasificación | Incierto | Directa = API |
|---|---|---|---:|---:|---:|---|---|---|
{chr(10).join(result_rows)}

## A. Conclusión de integración

{payload['integration_matches']}/{payload['sample_size']} casos coincidieron entre inferencia directa y `POST /predict`. La máxima diferencia absoluta observada fue `{payload['max_score_absolute_difference']:.10g}`. Coincidieron orden de clases, categoría, las tres puntuaciones y el estado de incertidumbre. Este resultado valida el cableado para la muestra, no la exactitud agronómica.

## B. Conclusión de clasificación

La predicción coincidió con la etiqueta auditada en {payload['classification_correct']}/{payload['sample_size']} casos y difirió en {payload['classification_errors']}/{payload['sample_size']}. Hay {payload['uncertain_count']} resultados por debajo de 0.70. Son conteos descriptivos de una muestra pequeña de VAL seleccionada para integración; no sustituyen las métricas completas de VAL ni TEST.

Errores conservados:

{incorrect_lines}

Resultados inciertos:

{uncertain_lines}

## Casos indicados para la comprobación manual en navegador

{browser_rows}

### Estado y recorrido manual

La comprobación visual no forma parte del script. En esta ejecución quedó **pendiente** porque el inventario de automatización devolvió cero navegadores y cero aplicaciones controlables. No se afirman clics ni verificaciones visuales.

Con backend y frontend locales activos, abrir `http://127.0.0.1:3000` y seguir este recorrido:

1. Subir `data/raw/coffee___healthy/C4P26H1.jpg`, pulsar **Analizar hoja** y comprobar que la vista previa conserva ese nombre. Debe aparecer **Resultado incierto**, con **Categoría más probable: Hoja sana** y puntuaciones aproximadas 0.634767 / 0.249167 / 0.116066 en orden sana / ácaro rojo / roya.
2. Reemplazarla por `data/raw/coffee___red_spider_mite/C11P37E2.jpg`. Comprobar que el resultado anterior desaparece y que la vista previa cambia antes de analizar. Debe aparecer **Clasificación orientativa: Roya**, con puntuaciones aproximadas 0.026080 / 0.256660 / 0.717260. Es un error de clasificación conservado: la etiqueta auditada es ácaro rojo.
3. Pulsar **Analizar otra fotografía** y verificar que se limpian archivo, vista previa y resultado. Subir `data/raw/coffee___rust/C8P3H1.jpg` y analizar. Debe aparecer **Clasificación orientativa: Roya**, con puntuaciones aproximadas 0.019804 / 0.096846 / 0.883350.
4. Para probar sustitución durante una petición, iniciar el análisis de cualquiera de los tres archivos y seleccionar otro antes de recibir respuesta. La interfaz debe cancelar o invalidar la solicitud anterior y nunca mostrar un resultado asociado a la fotografía reemplazada.

Las diferencias visuales de redondeo deben limitarse al formato porcentual de la interfaz. Las fotografías permanecen en `data/raw`, no se copian a la guía y no se versionan en Git.
"""


def run_command(
    selection_path: Path,
    output_dir: Path,
    report_path: Path,
    checkpoint_path: Path,
    base_url: str,
) -> None:
    if sha256_file(MANIFEST_PATH) != EXPECTED_MANIFEST_SHA256:
        raise RuntimeError("El manifiesto cambió antes de ejecutar la comprobación")
    if sha256_file(checkpoint_path) != EXPECTED_CHECKPOINT_SHA256:
        raise RuntimeError("El checkpoint activo no coincide con el SHA256 fijado")

    selection = validate_fixed_selection(selection_path)
    selection_hash = sha256_file(selection_path)
    model, checkpoint = load_checkpoint(checkpoint_path)
    if checkpoint.get("classes") != CLASS_ORDER:
        raise RuntimeError(f"Orden de clases inesperado: {checkpoint.get('classes')}")
    if checkpoint.get("manifest_sha256") != EXPECTED_MANIFEST_SHA256:
        raise RuntimeError("El checkpoint no corresponde al manifiesto fijado")

    health_status, health = get_json(base_url, "/health")
    health_checks = {
        "http_200": health_status == 200,
        "model_loaded": health.get("model_loaded") is True,
        "checkpoint_sha256": health.get("checkpoint_sha256") == EXPECTED_CHECKPOINT_SHA256,
        "class_order": health.get("classes") == CLASS_ORDER,
        "uncertainty_threshold": health.get("uncertainty_threshold") == UNCERTAINTY_THRESHOLD,
    }
    if not all(health_checks.values()):
        raise RuntimeError(f"El backend no corresponde al contrato fijado: {health_checks}")

    results: list[dict[str, Any]] = []
    for selected in selection:
        image_path = ROOT / selected["path"]
        direct = direct_scores(model, image_path)
        api_status, api_payload = post_file(
            base_url,
            filename=image_path.name,
            content_type="image/jpeg",
            data=image_path.read_bytes(),
        )
        if api_status != 200:
            raise RuntimeError(f"POST /predict devolvió {api_status} para {selected['path']}")

        api_score_items = api_payload.get("scores", [])
        api_categories = [item.get("category") for item in api_score_items]
        api_by_class = score_map(api_score_items)
        if api_categories != CLASS_ORDER or set(api_by_class) != set(CLASS_ORDER):
            raise RuntimeError(f"Orden/puntuaciones API inesperados: {selected['path']}")

        differences = {
            category: abs(float(direct[index]) - api_by_class[category])
            for index, category in enumerate(CLASS_ORDER)
        }
        direct_index = max(range(len(direct)), key=direct.__getitem__)
        direct_category = CLASS_ORDER[direct_index]
        direct_uncertain = float(direct[direct_index]) < UNCERTAINTY_THRESHOLD
        integration_checks = {
            "score_order": api_categories == CLASS_ORDER,
            "category": api_payload.get("category") == direct_category,
            "scores": max(differences.values()) <= SCORE_ABSOLUTE_TOLERANCE,
            "uncertainty": api_payload.get("is_uncertain") == direct_uncertain,
            "threshold": api_payload.get("uncertainty_threshold") == UNCERTAINTY_THRESHOLD,
        }
        integration_agreement = all(integration_checks.values())
        results.append(
            {
                "selection_index": int(selected["selection_index"]),
                "path": selected["path"],
                "filename": selected["filename"],
                "group": selected["group"],
                "true_label": selected["label"],
                "true_label_display": selected["label_display"],
                "original_classification": selected["original_classification"],
                "annotation_id": selected["annotation_id"],
                "predicted_label": api_payload["category"],
                "predicted_label_display": api_payload["category_label"],
                "top_score": float(api_payload["score"]),
                "direct_scores": dict(zip(CLASS_ORDER, direct, strict=True)),
                "api_scores": api_by_class,
                "score_absolute_differences": differences,
                "max_score_absolute_difference": max(differences.values()),
                "classification_correct": api_payload["category"] == selected["label"],
                "is_uncertain": bool(api_payload["is_uncertain"]),
                "integration_checks": integration_checks,
                "integration_agreement": integration_agreement,
            }
        )

    if not all(row["integration_agreement"] for row in results):
        failed = [row["path"] for row in results if not row["integration_agreement"]]
        raise RuntimeError(f"La integración discrepa en: {failed}")

    browser_candidates: list[dict[str, str]] = []
    for category in CLASS_ORDER:
        row = next(item for item in results if item["true_label"] == category)
        browser_candidates.append(
            {"purpose": f"ejemplo con etiqueta {DISPLAY_NAMES[category]}", "path": row["path"]}
        )
    first_uncertain = next((row for row in results if row["is_uncertain"]), None)
    if first_uncertain is not None:
        browser_candidates.append(
            {"purpose": "resultado incierto de la selección", "path": first_uncertain["path"]}
        )
    first_error = next((row for row in results if not row["classification_correct"]), None)
    if first_error is not None:
        browser_candidates.append(
            {"purpose": "clasificación incorrecta de la selección", "path": first_error["path"]}
        )

    payload: dict[str, Any] = {
        "scope": "VAL integration sample; not independent evaluation; TEST not consulted",
        "api_base_url": base_url,
        "selection_sha256": selection_hash,
        "checkpoint_path": str(checkpoint_path.relative_to(ROOT)).replace("\\", "/"),
        "checkpoint_sha256": EXPECTED_CHECKPOINT_SHA256,
        "manifest_sha256": EXPECTED_MANIFEST_SHA256,
        "class_order": CLASS_ORDER,
        "preprocessing": {
            "orientation": "ImageOps.exif_transpose",
            "color": "RGB",
            "resize": [224, 224],
            "tensor": "ToTensor",
            "normalization_mean": [0.485, 0.456, 0.406],
            "normalization_std": [0.229, 0.224, 0.225],
        },
        "uncertainty_threshold": UNCERTAINTY_THRESHOLD,
        "score_absolute_tolerance": SCORE_ABSOLUTE_TOLERANCE,
        "api_health": health,
        "health_checks": health_checks,
        "sample_size": len(results),
        "integration_matches": sum(row["integration_agreement"] for row in results),
        "classification_correct": sum(row["classification_correct"] for row in results),
        "classification_errors": sum(not row["classification_correct"] for row in results),
        "uncertain_count": sum(row["is_uncertain"] for row in results),
        "max_score_absolute_difference": max(
            row["max_score_absolute_difference"] for row in results
        ),
        "browser_candidates": browser_candidates,
        "results": results,
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    result_fields = [
        "selection_index",
        "path",
        "filename",
        "group",
        "true_label",
        "true_label_display",
        "original_classification",
        "predicted_label",
        "predicted_label_display",
        "score_healthy",
        "score_red_spider_mite",
        "score_rust",
        "classification_correct",
        "is_uncertain",
        "integration_agreement",
        "max_score_absolute_difference",
    ]
    csv_rows = [
        {
            "selection_index": row["selection_index"],
            "path": row["path"],
            "filename": row["filename"],
            "group": row["group"],
            "true_label": row["true_label"],
            "true_label_display": row["true_label_display"],
            "original_classification": row["original_classification"],
            "predicted_label": row["predicted_label"],
            "predicted_label_display": row["predicted_label_display"],
            "score_healthy": row["api_scores"]["coffee___healthy"],
            "score_red_spider_mite": row["api_scores"]["coffee___red_spider_mite"],
            "score_rust": row["api_scores"]["coffee___rust"],
            "classification_correct": row["classification_correct"],
            "is_uncertain": row["is_uncertain"],
            "integration_agreement": row["integration_agreement"],
            "max_score_absolute_difference": row["max_score_absolute_difference"],
        }
        for row in results
    ]
    write_csv(output_dir / "results.csv", csv_rows, result_fields)
    write_json(output_dir / "results.json", payload)
    report_path.write_text(markdown_report(payload), encoding="utf-8")
    print(json.dumps({key: value for key, value in payload.items() if key != "results"}, ensure_ascii=False, indent=2))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    select_parser = subparsers.add_parser("select", help="Fija 15 imágenes sin cargar el modelo")
    select_parser.add_argument("--selection", type=Path, default=DEFAULT_SELECTION_PATH)
    select_parser.add_argument("--metadata", type=Path, default=DEFAULT_SELECTION_METADATA_PATH)

    run_parser = subparsers.add_parser("run", help="Compara inferencia directa con la API")
    run_parser.add_argument("--selection", type=Path, default=DEFAULT_SELECTION_PATH)
    run_parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    run_parser.add_argument("--report", type=Path, default=DEFAULT_REPORT_PATH)
    run_parser.add_argument("--checkpoint", type=Path, default=DEFAULT_CHECKPOINT_PATH)
    run_parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    return parser.parse_args()


def resolve_from_root(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def main() -> None:
    args = parse_args()
    if args.command == "select":
        select_command(resolve_from_root(args.selection), resolve_from_root(args.metadata))
        return
    run_command(
        selection_path=resolve_from_root(args.selection),
        output_dir=resolve_from_root(args.output_dir),
        report_path=resolve_from_root(args.report),
        checkpoint_path=resolve_from_root(args.checkpoint),
        base_url=args.base_url,
    )


if __name__ == "__main__":
    main()
