from __future__ import annotations

"""Audita CoffeeLeaf-CO v2 y fija subconjuntos para el filtro de dominio.

El script no entrena, no modifica el dataset de CafeIA y no abre imagenes de
TEST de RoCoLe. Solo compara contra los SHA256 ya registrados en el manifiesto
local para detectar solapamientos exactos.
"""

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from src.common import ROOT


EXPECTED_ZIP_MD5 = "2ba46bd8f7a23708d982ff578760f1fa"
EXPECTED_MANIFEST_TOTAL = 2769
EXPECTED_INCLUDED_TOTAL = 2315
EXPECTED_MANIFEST_SOURCE_COUNTS = {
    "own_field": 1705,
    "rust_and_leaf_miner": 610,
    "rocole": 454,
}
EXPECTED_INCLUDED_SOURCE_COUNTS = {"own_field": 1705, "rust_and_leaf_miner": 610}
EXPECTED_SPLIT_COUNTS = {"train": 1618, "val": 348, "test": 349}
REQUIRED_COLUMNS = {
    "filename",
    "split",
    "inferred_source",
    "provenance_evidence",
    "sha256",
    "n_annotations",
    "class_ids_present",
    "width",
    "height",
}


def digest_file(path: Path, algorithm: str) -> str:
    digest = hashlib.new(algorithm)
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_manifest(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        columns = set(reader.fieldnames or [])
        missing = REQUIRED_COLUMNS - columns
        if missing:
            raise ValueError(f"El manifiesto oficial carece de columnas: {sorted(missing)}")
        rows = [{key: value or "" for key, value in row.items()} for row in reader]
    if len(rows) != EXPECTED_MANIFEST_TOTAL:
        raise ValueError(
            f"Se esperaban {EXPECTED_MANIFEST_TOTAL} filas del manifiesto publicado y "
            f"se obtuvieron {len(rows)}"
        )
    return rows


def read_rocole_hashes(path: Path) -> tuple[set[str], set[str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows or not {"split", "sha256"}.issubset(rows[0]):
        raise ValueError("El manifiesto de RoCoLe no contiene split y sha256")
    test_hashes = {row["sha256"].lower() for row in rows if row["split"] == "test"}
    development_hashes = {
        row["sha256"].lower() for row in rows if row["split"] in {"train", "val"}
    }
    return test_hashes, development_hashes


def validate_yolo_label(path: Path, expected_count: int, expected_ids: set[int]) -> None:
    lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if len(lines) != expected_count:
        raise ValueError(
            f"{path}: se declararon {expected_count} anotaciones y hay {len(lines)} lineas"
        )
    observed_ids: set[int] = set()
    for line_number, line in enumerate(lines, start=1):
        parts = line.split()
        if len(parts) != 5:
            raise ValueError(f"{path}:{line_number}: una caja YOLO debe tener cinco valores")
        class_id = int(parts[0])
        coordinates = [float(value) for value in parts[1:]]
        if class_id not in {0, 1, 2}:
            raise ValueError(f"{path}:{line_number}: clase inesperada {class_id}")
        if any(value < 0.0 or value > 1.0 for value in coordinates):
            raise ValueError(f"{path}:{line_number}: coordenada fuera de [0, 1]")
        observed_ids.add(class_id)
    if observed_ids != expected_ids:
        raise ValueError(
            f"{path}: class_ids_present={sorted(expected_ids)} pero las cajas usan "
            f"{sorted(observed_ids)}"
        )


def write_manifest(path: Path, rows: list[dict[str, str]], reference: bool) -> None:
    fields = [
        "path",
        "source",
        "sha256",
        "label",
        "original_filename",
        "manifest_split",
        "actual_split",
        "n_annotations",
        "class_ids_present",
    ]
    if reference:
        fields.insert(2, "eligible_for_domain_guard")
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Audita CoffeeLeaf-CO v2 sin usar TEST de RoCoLe")
    parser.add_argument("--dataset-root", type=Path, required=True)
    parser.add_argument("--source-zip", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--rocole-manifest",
        type=Path,
        default=ROOT / "data" / "processed" / "manifest.csv",
    )
    args = parser.parse_args()

    dataset_root = args.dataset_root.resolve()
    source_zip = args.source_zip.resolve()
    output_dir = args.output_dir.resolve()
    rocole_manifest = args.rocole_manifest.resolve()
    if output_dir.exists():
        raise FileExistsError(f"No se sobrescribe la salida existente: {output_dir}")
    if not dataset_root.is_dir() or not source_zip.is_file():
        raise FileNotFoundError("No se encontro el dataset extraido o su ZIP de procedencia")
    zip_md5 = digest_file(source_zip, "md5")
    if zip_md5 != EXPECTED_ZIP_MD5:
        raise RuntimeError(f"MD5 del ZIP inesperado: {zip_md5}")

    manifest_path = dataset_root / "provenance_manifest.csv"
    rows = read_manifest(manifest_path)
    test_hashes, development_hashes = read_rocole_hashes(rocole_manifest)

    filenames = [row["filename"] for row in rows]
    duplicate_names = [name for name, count in Counter(filenames).items() if count > 1]
    if duplicate_names:
        raise ValueError(
            "El manifiesto publicado contiene nombres duplicados no resolubles: "
            f"{duplicate_names[:5]}"
        )

    actual_locations: dict[str, str] = {}
    for actual_split in EXPECTED_SPLIT_COUNTS:
        for image_path in (dataset_root / "images" / actual_split).iterdir():
            if not image_path.is_file():
                continue
            if image_path.name in actual_locations:
                raise ValueError(f"La imagen aparece en mas de una carpeta: {image_path.name}")
            actual_locations[image_path.name] = actual_split
    if len(actual_locations) != EXPECTED_INCLUDED_TOTAL:
        raise ValueError(
            f"Se esperaban {EXPECTED_INCLUDED_TOTAL} imagenes extraidas y se obtuvieron "
            f"{len(actual_locations)}"
        )

    source_counts: Counter[str] = Counter()
    included_source_counts: Counter[str] = Counter()
    split_counts: Counter[str] = Counter()
    own_split_counts: Counter[str] = Counter()
    formats: Counter[str] = Counter()
    references: list[dict[str, str]] = []
    reserved: list[dict[str, str]] = []
    rocole_test_collisions: list[str] = []
    rocole_development_collisions: list[str] = []
    excluded_rocole_rows = 0
    manifest_split_mismatches = 0
    documented_corrections_applied = 0
    included_hashes: list[str] = []
    matched_actual_files: set[str] = set()

    for index, row in enumerate(rows, start=2):
        filename = Path(row["filename"]).name
        if filename != row["filename"] or Path(filename).suffix.lower() not in {".jpg", ".jpeg", ".png"}:
            raise ValueError(f"Fila {index}: nombre de imagen no admitido {row['filename']!r}")
        manifest_split = row["split"]
        source = row["inferred_source"]
        source_counts[source] += 1
        if manifest_split not in EXPECTED_SPLIT_COUNTS or source not in EXPECTED_MANIFEST_SOURCE_COUNTS:
            raise ValueError(
                f"Fila {index}: split/source inesperado: {manifest_split}/{source}"
            )
        if filename not in actual_locations:
            if source != "rocole":
                raise FileNotFoundError(
                    f"El manifiesto declara una imagen no incluida y no RoCoLe: {filename}"
                )
            excluded_rocole_rows += 1
            continue
        if source == "rocole":
            raise ValueError(f"La version final todavia incluye una imagen RoCoLe: {filename}")
        actual_split = actual_locations[filename]
        matched_actual_files.add(filename)
        if manifest_split != actual_split:
            manifest_split_mismatches += 1
        expected_sha = row["sha256"].lower()
        if len(expected_sha) != 64 or any(character not in "0123456789abcdef" for character in expected_sha):
            raise ValueError(f"Fila {index}: SHA256 invalido")

        image_path = dataset_root / "images" / actual_split / filename
        label_path = dataset_root / "labels" / actual_split / f"{Path(filename).stem}.txt"
        if not image_path.is_file() or not label_path.is_file():
            raise FileNotFoundError(f"Falta la imagen o etiqueta declarada: {filename}")
        actual_sha = digest_file(image_path, "sha256")
        if actual_sha != expected_sha:
            raise RuntimeError(f"SHA256 no coincide para {filename}")
        try:
            with Image.open(image_path) as image:
                image.verify()
            with Image.open(image_path) as image:
                width, height = image.size
                formats[image.format or "unknown"] += 1
        except (UnidentifiedImageError, OSError, SyntaxError, ValueError) as exc:
            raise ValueError(f"Imagen invalida {filename}: {exc}") from exc
        if (width, height) != (int(row["width"]), int(row["height"])):
            raise ValueError(f"Dimensiones distintas a las declaradas para {filename}")

        manifest_class_ids = {
            int(value) for value in row["class_ids_present"].split(";") if value
        }
        # El manifiesto conserva los IDs anteriores; DATASET_CARD.md documenta
        # que minador fue remapeado de 3 a 2 en el conjunto final.
        class_ids = {2 if value == 3 else value for value in manifest_class_ids}
        annotation_count = int(row["n_annotations"])
        validation_count = annotation_count
        validation_class_ids = class_ids
        if filename == "MINEIRO_111.jpg":
            if actual_split != "test" or annotation_count != 9 or class_ids != {1, 2}:
                raise ValueError("MINEIRO_111 no coincide con CORRECTIONS.md")
            validation_count = 8
            validation_class_ids = {2}
            documented_corrections_applied += 1
        validate_yolo_label(label_path, validation_count, validation_class_ids)
        included_source_counts[source] += 1
        split_counts[actual_split] += 1
        included_hashes.append(expected_sha)
        if expected_sha in test_hashes:
            rocole_test_collisions.append(filename)
        if expected_sha in development_hashes:
            rocole_development_collisions.append(filename)

        if source != "own_field":
            continue
        own_split_counts[actual_split] += 1
        base = {
            "path": f"images/{actual_split}/{filename}",
            "source": f"coffeeleaf_own_field_{actual_split}",
            "sha256": expected_sha,
            "label": "coffee_positive_domain_only",
            "original_filename": filename,
            "manifest_split": manifest_split,
            "actual_split": actual_split,
            "n_annotations": str(annotation_count),
            "class_ids_present": row["class_ids_present"],
        }
        if actual_split == "train":
            references.append({
                **base,
                "source": "own_field",
                "eligible_for_domain_guard": "true",
            })
        else:
            reserved.append(base)

    if dict(source_counts) != EXPECTED_MANIFEST_SOURCE_COUNTS:
        raise ValueError(f"Conteos por fuente inesperados: {dict(source_counts)}")
    if dict(included_source_counts) != EXPECTED_INCLUDED_SOURCE_COUNTS:
        raise ValueError(
            f"Conteos incluidos por fuente inesperados: {dict(included_source_counts)}"
        )
    if dict(split_counts) != EXPECTED_SPLIT_COUNTS:
        raise ValueError(f"Conteos por split inesperados: {dict(split_counts)}")
    if rocole_test_collisions or rocole_development_collisions:
        raise ValueError(
            "Se detectaron coincidencias SHA256 con RoCoLe: "
            f"TEST={rocole_test_collisions[:5]}, TRAIN/VAL={rocole_development_collisions[:5]}"
        )
    if matched_actual_files != set(actual_locations):
        missing = sorted(set(actual_locations) - matched_actual_files)
        raise ValueError(f"Hay imagenes finales sin fila de procedencia: {missing[:5]}")
    duplicate_included_hashes = [
        value for value, count in Counter(included_hashes).items() if count > 1
    ]
    if duplicate_included_hashes:
        raise ValueError(
            "Las imagenes incluidas contienen duplicados SHA256: "
            f"{duplicate_included_hashes[:5]}"
        )

    output_dir.mkdir(parents=True, exist_ok=False)
    reference_path = output_dir / "coffeeleaf_train_references.csv"
    reserved_path = output_dir / "coffeeleaf_reserved_val_test.csv"
    write_manifest(reference_path, references, reference=True)
    write_manifest(reserved_path, reserved, reference=False)
    summary = {
        "status": "audited_not_integrated",
        "source": {
            "title": "DECAFIA / CoffeeLeaf-CO v2.0.0",
            "doi": "10.5281/zenodo.22756170",
            "license": "CC BY 4.0",
            "zip_size_bytes": source_zip.stat().st_size,
            "zip_md5": zip_md5,
            "zip_sha256": digest_file(source_zip, "sha256"),
            "official_manifest_sha256": digest_file(manifest_path, "sha256"),
        },
        "verified": {
            "manifest_rows": len(rows),
            "included_images": len(matched_actual_files),
            "excluded_rocole_manifest_rows": excluded_rocole_rows,
            "manifest_split_mismatches": manifest_split_mismatches,
            "documented_corrections_applied": documented_corrections_applied,
            "per_file_sha256": True,
            "image_dimensions": True,
            "yolo_annotation_counts_and_classes": True,
            "source_counts": dict(sorted(source_counts.items())),
            "included_source_counts": dict(sorted(included_source_counts.items())),
            "split_counts": dict(sorted(split_counts.items())),
            "own_field_split_counts": dict(sorted(own_split_counts.items())),
            "formats": dict(sorted(formats.items())),
            "exact_duplicate_filenames": 0,
            "exact_duplicate_sha256": 0,
            "rocole_test_hash_collisions": 0,
            "rocole_train_val_hash_collisions": 0,
            "rocole_test_images_opened": 0,
        },
        "roles": {
            "candidate_references": {"split": "train", "count": len(references)},
            "reserved_positive_check": {"splits": ["val", "test"], "count": len(reserved)},
            "classification_labels_created": False,
        },
        "outputs": {
            "reference_manifest": reference_path.name,
            "reference_manifest_sha256": digest_file(reference_path, "sha256"),
            "reserved_manifest": reserved_path.name,
            "reserved_manifest_sha256": digest_file(reserved_path, "sha256"),
        },
        "limitations": [
            "El manifiesto publicado conserva 454 filas de RoCoLe excluidas del ZIP final.",
            "La columna split del manifiesto publicado no corresponde a las carpetas finales; los roles usan la ubicacion real del archivo.",
            "MINEIRO_111 se valido contra la correccion documentada en CORRECTIONS.md porque el manifiesto conserva el conteo anterior.",
            "Las particiones son por imagen y la fuente no publica identificadores de planta o sesion.",
            "VAL y TEST de CoffeeLeaf-CO comparten la procedencia del desarrollo y no son una validacion biologicamente independiente.",
            "Las cajas de deteccion no se convirtieron en etiquetas de hoja completa.",
            "La ausencia de coincidencias SHA256 no descarta copias recodificadas o recortadas.",
        ],
    }
    (output_dir / "audit_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
