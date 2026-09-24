"""Compara RoCoLe original con TRAIN/VAL y los conflictos excluidos.

La politica de este script es deliberadamente restrictiva:

* nunca abre imagenes que el manifiesto marque como ``test``;
* no decodifica ni conserva anotaciones de ``test``;
* usa SHA-256 como prueba de identidad byte a byte;
* cuando la copia derivada fue redimensionada, registra por separado una
  similitud numerica de contenido. Esa similitud no se presenta como SHA-256.

El script solo escribe evidencias dentro del directorio indicado por
``--output-dir``. No modifica el dataset, el manifiesto ni los checkpoints.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import zipfile
from collections import Counter, defaultdict
from pathlib import Path, PurePosixPath
from typing import Any

import numpy as np
from PIL import Image


ALLOWED_SPLITS = {"train", "val"}
ORIGINAL_TO_LOCAL = {
    "healthy": "coffee___healthy",
    "red_spider_mite": "coffee___red_spider_mite",
    "rust_level_1": "coffee___rust",
    "rust_level_2": "coffee___rust",
    "rust_level_3": "coffee___rust",
    "rust_level_4": "coffee___rust",
}
RUST_LEVELS = {
    "rust_level_1": "roya (nivel original 1: 1-5 %)",
    "rust_level_2": "roya (nivel original 2: 6-20 %)",
    "rust_level_3": "roya (nivel original 3: 21-50 %)",
    "rust_level_4": "roya (nivel original 4: >50 %)",
}


def sha256_bytes(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalized_gray(blob: bytes) -> np.ndarray:
    with Image.open(io.BytesIO(blob)) as image:
        return np.asarray(
            image.convert("L").resize((128, 72), Image.Resampling.LANCZOS),
            dtype=np.float32,
        )


def content_similarity(left: bytes, right: bytes) -> tuple[float, float]:
    """Devuelve correlacion de Pearson y error absoluto medio a 128x72."""
    a = normalized_gray(left).ravel()
    b = normalized_gray(right).ravel()
    if float(a.std()) == 0.0 or float(b.std()) == 0.0:
        correlation = 1.0 if np.array_equal(a, b) else 0.0
    else:
        correlation = float(np.corrcoef(a, b)[0, 1])
    mae = float(np.mean(np.abs(a - b)))
    return correlation, mae


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"No hay filas para escribir en {path}")
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def load_manifest(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        selected = [row for row in csv.DictReader(handle) if row["split"] in ALLOWED_SPLITS]
    if not selected:
        raise ValueError("El manifiesto no contiene filas TRAIN/VAL")
    if any(row["split"] not in ALLOWED_SPLITS for row in selected):
        raise AssertionError("La seleccion incluyo una particion no autorizada")
    return selected


def load_conflicts(path: Path) -> list[list[str]]:
    report = json.loads(path.read_text(encoding="utf-8"))
    conflicts = report["conflicts"]
    if sum(len(pair) for pair in conflicts) != report["conflicting_files_excluded"]:
        raise ValueError("El recuento de conflictos no coincide con dataset_audit.json")
    return conflicts


def photo_entries(archive: zipfile.ZipFile) -> dict[str, zipfile.ZipInfo]:
    entries: dict[str, zipfile.ZipInfo] = {}
    for info in archive.infolist():
        if "/Photos/" not in info.filename or PurePosixPath(info.filename).suffix.lower() != ".jpg":
            continue
        name = PurePosixPath(info.filename).name
        if name in entries:
            raise ValueError(f"Nombre original duplicado dentro del ZIP: {name}")
        entries[name] = info
    return entries


def annotation_rows(path: Path, requested: set[str]) -> dict[str, list[dict[str, str]]]:
    """Lee el CSV secuencialmente, pero solo decodifica etiquetas solicitadas."""
    selected: dict[str, list[dict[str, str]]] = defaultdict(list)
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            name = row["External ID"]
            if name not in requested:
                continue
            label = json.loads(row["Label"])
            selected[name].append(
                {
                    "classification": label.get("classification", ""),
                    "annotation_id": row["ID"],
                    "data_row_id": row["DataRow ID"],
                }
            )
    return selected


def relation_status(raw_equal: bool, name_unique: bool, correlation: float, mae: float) -> str:
    if raw_equal:
        return "exact_sha256"
    # Umbral conservador para documentar una copia redimensionada. No equivale
    # a identidad byte a byte y siempre se acompana de nombre original unico.
    if name_unique and correlation >= 0.995 and mae <= 2.0:
        return "derived_content_consistent"
    return "ambiguous_or_low_similarity"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--original-zip", type=Path, required=True)
    parser.add_argument("--annotations-csv", type=Path, required=True)
    parser.add_argument("--local-source-zip", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    root = args.project_root.resolve()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    manifest_path = root / "data" / "processed" / "manifest.csv"
    dataset_audit_path = root / "reports" / "dataset_audit.json"
    manifest_rows = load_manifest(manifest_path)
    conflicts = load_conflicts(dataset_audit_path)

    train_val_names = {PurePosixPath(row["path"]).name for row in manifest_rows}
    conflict_paths = [path for pair in conflicts for path in pair]
    conflict_names = {PurePosixPath(path).name for path in conflict_paths}
    if train_val_names & conflict_names:
        raise ValueError("Un archivo excluido aparece tambien en TRAIN/VAL")
    requested_names = train_val_names | conflict_names

    with zipfile.ZipFile(args.original_zip) as original_archive:
        original_photos = photo_entries(original_archive)
        original_photo_count = len(original_photos)
        missing_original_names = sorted(requested_names - set(original_photos))

        annotations = annotation_rows(args.annotations_csv, requested_names)
        annotation_missing = sorted(requested_names - set(annotations))
        annotation_ambiguous = sorted(name for name, rows in annotations.items() if len(rows) != 1)

        original_blobs: dict[str, bytes] = {}
        original_hashes: dict[str, str] = {}
        for name in sorted(requested_names & set(original_photos)):
            blob = original_archive.read(original_photos[name])
            original_blobs[name] = blob
            original_hashes[name] = sha256_bytes(blob)

    selected_hash_to_names: dict[str, list[str]] = defaultdict(list)
    for name, digest in original_hashes.items():
        selected_hash_to_names[digest].append(name)
    ambiguous_original_hashes = {
        digest: sorted(names) for digest, names in selected_hash_to_names.items() if len(names) > 1
    }

    comparison_rows: list[dict[str, Any]] = []
    for row in manifest_rows:
        if row["split"] not in ALLOWED_SPLITS:
            raise AssertionError("Intento de procesar una imagen fuera de TRAIN/VAL")
        local_path = root / PurePosixPath(row["path"])
        local_blob = local_path.read_bytes()
        local_hash = sha256_bytes(local_blob)
        if local_hash != row["sha256"]:
            raise ValueError(f"SHA local distinto al manifiesto: {row['path']}")
        name = local_path.name
        original_blob = original_blobs.get(name)
        annotation_candidates = annotations.get(name, [])
        annotation = annotation_candidates[0] if len(annotation_candidates) == 1 else None

        if original_blob is None:
            original_hash = ""
            raw_equal = False
            correlation = math.nan
            mae = math.nan
            status = "no_original_name_match"
        else:
            original_hash = original_hashes[name]
            raw_equal = local_hash == original_hash
            correlation, mae = content_similarity(local_blob, original_blob)
            status = relation_status(
                raw_equal,
                len(selected_hash_to_names[original_hash]) == 1,
                correlation,
                mae,
            )

        original_label = annotation["classification"] if annotation else ""
        converted_label = ORIGINAL_TO_LOCAL.get(original_label, "")
        comparison_rows.append(
            {
                "split": row["split"],
                "local_path": row["path"],
                "external_id": name,
                "local_sha256": local_hash,
                "original_sha256": original_hash,
                "raw_sha256_match": raw_equal,
                "content_correlation_128x72": "" if math.isnan(correlation) else f"{correlation:.9f}",
                "content_mae_128x72": "" if math.isnan(mae) else f"{mae:.6f}",
                "relation_status": status,
                "original_classification": original_label,
                "converted_local_class": converted_label,
                "local_class": row["label"],
                "label_match_after_conversion": bool(converted_label) and converted_label == row["label"],
                "annotation_row_count": len(annotation_candidates),
                "annotation_id": annotation["annotation_id"] if annotation else "",
            }
        )

    conflict_rows: list[dict[str, Any]] = []
    with zipfile.ZipFile(args.local_source_zip) as local_archive:
        local_entry_names = set(local_archive.namelist())
        for pair_index, pair in enumerate(conflicts, start=1):
            for local_archive_path in pair:
                if local_archive_path not in local_entry_names:
                    raise ValueError(f"No existe en el ZIP local: {local_archive_path}")
                local_blob = local_archive.read(local_archive_path)
                local_hash = sha256_bytes(local_blob)
                name = PurePosixPath(local_archive_path).name
                original_blob = original_blobs.get(name)
                annotation_candidates = annotations.get(name, [])
                annotation = annotation_candidates[0] if len(annotation_candidates) == 1 else None

                if original_blob is None:
                    original_hash = ""
                    raw_equal = False
                    correlation = math.nan
                    mae = math.nan
                    status = "no_original_name_match"
                else:
                    original_hash = original_hashes[name]
                    raw_equal = local_hash == original_hash
                    correlation, mae = content_similarity(local_blob, original_blob)
                    status = relation_status(
                        raw_equal,
                        len(selected_hash_to_names[original_hash]) == 1,
                        correlation,
                        mae,
                    )

                original_label = annotation["classification"] if annotation else ""
                converted_label = ORIGINAL_TO_LOCAL.get(original_label, "")
                local_label = PurePosixPath(local_archive_path).parent.name
                conflict_rows.append(
                    {
                        "conflict_pair": pair_index,
                        "local_archive_path": local_archive_path,
                        "external_id": name,
                        "local_sha256": local_hash,
                        "original_sha256": original_hash,
                        "raw_sha256_match": raw_equal,
                        "content_correlation_128x72": "" if math.isnan(correlation) else f"{correlation:.9f}",
                        "content_mae_128x72": "" if math.isnan(mae) else f"{mae:.6f}",
                        "relation_status": status,
                        "original_classification": original_label,
                        "converted_local_class": converted_label,
                        "local_folder_class": local_label,
                        "folder_label_matches_annotation": bool(converted_label)
                        and converted_label == local_label,
                        "annotation_row_count": len(annotation_candidates),
                        "annotation_id": annotation["annotation_id"] if annotation else "",
                    }
                )

    pair_diagnostics: list[dict[str, Any]] = []
    for pair_index in range(1, len(conflicts) + 1):
        pair_rows = [row for row in conflict_rows if row["conflict_pair"] == pair_index]
        pair_diagnostics.append(
            {
                "conflict_pair": pair_index,
                "local_hashes_identical": len({row["local_sha256"] for row in pair_rows}) == 1,
                "original_hashes_distinct": len({row["original_sha256"] for row in pair_rows})
                == len(pair_rows),
                "original_labels_distinct_after_conversion": len(
                    {row["converted_local_class"] for row in pair_rows}
                )
                == len(pair_rows),
                "both_original_annotations_match_folder_names": all(
                    row["folder_label_matches_annotation"] for row in pair_rows
                ),
            }
        )

    write_csv(output_dir / "train_val_annotation_comparison.csv", comparison_rows)
    write_csv(output_dir / "excluded_conflicts_original_comparison.csv", conflict_rows)
    write_csv(output_dir / "excluded_conflict_pair_diagnostics.csv", pair_diagnostics)

    by_split: dict[str, Any] = {}
    for split in sorted(ALLOWED_SPLITS):
        rows = [row for row in comparison_rows if row["split"] == split]
        by_split[split] = {
            "files": len(rows),
            "exact_sha256_matches": sum(row["raw_sha256_match"] for row in rows),
            "derived_content_consistent": sum(
                row["relation_status"] == "derived_content_consistent" for row in rows
            ),
            "label_matches_after_conversion": sum(
                row["label_match_after_conversion"] for row in rows
            ),
            "label_discrepancies_after_conversion": sum(
                not row["label_match_after_conversion"] for row in rows
            ),
            "original_classification_counts": dict(
                sorted(Counter(row["original_classification"] for row in rows).items())
            ),
            "local_class_counts": dict(sorted(Counter(row["local_class"] for row in rows).items())),
        }

    correlations = [
        float(row["content_correlation_128x72"])
        for row in comparison_rows
        if row["content_correlation_128x72"] != ""
    ]
    maes = [
        float(row["content_mae_128x72"])
        for row in comparison_rows
        if row["content_mae_128x72"] != ""
    ]
    summary = {
        "policy": {
            "allowed_splits": sorted(ALLOWED_SPLITS),
            "test_images_opened": 0,
            "test_annotation_rows_decoded_or_compared": 0,
            "predictions_or_metrics_calculated": False,
        },
        "conversion": ORIGINAL_TO_LOCAL,
        "rust_level_meanings": RUST_LEVELS,
        "original_zip": {
            "path": str(args.original_zip.resolve()),
            "sha256": sha256_file(args.original_zip),
            "size_bytes": args.original_zip.stat().st_size,
            "photo_entries": original_photo_count,
        },
        "train_val": {
            "files": len(comparison_rows),
            "unique_external_id_matches": sum(
                row["relation_status"] != "no_original_name_match" for row in comparison_rows
            ),
            "exact_sha256_matches": sum(row["raw_sha256_match"] for row in comparison_rows),
            "derived_content_consistent": sum(
                row["relation_status"] == "derived_content_consistent"
                for row in comparison_rows
            ),
            "ambiguous_or_low_similarity": sum(
                row["relation_status"] == "ambiguous_or_low_similarity"
                for row in comparison_rows
            ),
            "label_matches_after_conversion": sum(
                row["label_match_after_conversion"] for row in comparison_rows
            ),
            "label_discrepancies_after_conversion": sum(
                not row["label_match_after_conversion"] for row in comparison_rows
            ),
            "content_correlation_min": min(correlations) if correlations else None,
            "content_correlation_max": max(correlations) if correlations else None,
            "content_mae_min": min(maes) if maes else None,
            "content_mae_max": max(maes) if maes else None,
            "by_split": by_split,
        },
        "excluded_conflicts": {
            "files": len(conflict_rows),
            "pairs": len(conflicts),
            "exact_sha256_matches": sum(row["raw_sha256_match"] for row in conflict_rows),
            "derived_content_consistent": sum(
                row["relation_status"] == "derived_content_consistent" for row in conflict_rows
            ),
            "folder_label_matches_original_annotation": sum(
                row["folder_label_matches_annotation"] for row in conflict_rows
            ),
            "pairs_with_identical_local_hashes": sum(
                row["local_hashes_identical"] for row in pair_diagnostics
            ),
            "pairs_with_distinct_original_hashes": sum(
                row["original_hashes_distinct"] for row in pair_diagnostics
            ),
            "pairs_with_both_original_annotations_matching_folder_names": sum(
                row["both_original_annotations_match_folder_names"] for row in pair_diagnostics
            ),
        },
        "unmatched_or_ambiguous": {
            "missing_original_names": missing_original_names,
            "missing_annotation_names": annotation_missing,
            "multiple_annotation_rows": annotation_ambiguous,
            "duplicate_original_sha256_within_authorized_scope": ambiguous_original_hashes,
        },
    }
    (output_dir / "annotation_audit_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
