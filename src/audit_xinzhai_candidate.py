"""Audita el candidato Xinzhai sin mezclarlo con los datos de CaféIA.

El script abre las imágenes externas y las de TRAIN/VAL para calcular hashes
perceptuales. De TEST solo lee los SHA256 ya registrados en el manifiesto; no
abre sus imágenes ni utiliza rutas, etiquetas, predicciones o métricas.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

import numpy as np
from PIL import ExifTags, Image, ImageOps


ROOT = Path(__file__).resolve().parents[1]
PUBLISHED_ARCHIVE_SIZE = 5_166_455_708
PUBLISHED_ARCHIVE_MD5 = "31403d6afd8c6c8e762159117a322912"
PHASH_THRESHOLD = 4


def digest(path: Path, algorithm: str = "sha256") -> str:
    result = hashlib.new(algorithm)
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def dct_matrix(size: int) -> np.ndarray:
    positions = np.arange(size, dtype=np.float64)
    frequencies = positions[:, None]
    matrix = np.cos(np.pi * (positions + 0.5) * frequencies / size)
    matrix[0] *= np.sqrt(1.0 / size)
    matrix[1:] *= np.sqrt(2.0 / size)
    return matrix


DCT_32 = dct_matrix(32)


def phash64(image: Image.Image) -> str:
    grayscale = ImageOps.exif_transpose(image).convert("L").resize(
        (32, 32), Image.Resampling.LANCZOS
    )
    pixels = np.asarray(grayscale, dtype=np.float64)
    coefficients = DCT_32 @ pixels @ DCT_32.T
    low = coefficients[:8, :8]
    median = float(np.median(low.flatten()[1:]))
    bits = (low > median).flatten()
    value = 0
    for bit in bits:
        value = (value << 1) | int(bit)
    return f"{value:016x}"


def hamming(first: str, second: str) -> int:
    return (int(first, 16) ^ int(second, 16)).bit_count()


def filename_timestamp(stem: str) -> datetime | None:
    patterns = (
        (r"^IMG_(\d{8})_(\d{6})$", "%Y%m%d%H%M%S"),
        (r"^IMG(\d{14})$", "%Y%m%d%H%M%S"),
        (r"^IMG(\d{14})_\d+$", "%Y%m%d%H%M%S"),
        (r"^IMG_(\d{8})_(\d{6})_edit_\d+$", "%Y%m%d%H%M%S"),
    )
    for pattern, date_format in patterns:
        match = re.fullmatch(pattern, stem)
        if match:
            value = "".join(match.groups())
            return datetime.strptime(value, date_format)
    return None


def read_classes(path: Path) -> list[str]:
    return [line.strip() for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]


def read_boxes(path: Path, class_names: list[str]) -> list[dict[str, Any]]:
    boxes: list[dict[str, Any]] = []
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        line = raw_line.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) != 5:
            raise ValueError(f"Formato YOLO inválido en {path.name}:{line_number}: {line}")
        class_id = int(parts[0])
        coordinates = [float(value) for value in parts[1:]]
        if not 0 <= class_id < len(class_names):
            raise ValueError(f"Clase fuera de rango en {path.name}:{line_number}: {class_id}")
        if any(value < 0 or value > 1 for value in coordinates) or any(
            value <= 0 for value in coordinates[2:]
        ):
            raise ValueError(f"Caja normalizada inválida en {path.name}:{line_number}")
        boxes.append(
            {
                "class_id": class_id,
                "class_name": class_names[class_id],
                "x_center": coordinates[0],
                "y_center": coordinates[1],
                "width": coordinates[2],
                "height": coordinates[3],
            }
        )
    return boxes


def exif_fields(image: Image.Image) -> dict[str, str]:
    decoded = {
        ExifTags.TAGS.get(tag, str(tag)): value for tag, value in image.getexif().items()
    }
    wanted = ("DateTime", "DateTimeOriginal", "DateTimeDigitized", "Make", "Model", "Software")
    return {name: str(decoded.get(name, "")) for name in wanted}


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def same_hash_pairs(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, list[str]] = defaultdict(list)
    for row in rows:
        groups[str(row["sha256"])].append(str(row["filename"]))
    pairs: list[dict[str, Any]] = []
    for sha256, filenames in groups.items():
        if len(filenames) < 2:
            continue
        for first_index, first in enumerate(filenames):
            for second in filenames[first_index + 1 :]:
                pairs.append({"sha256": sha256, "first": first, "second": second})
    return pairs


def perceptual_pairs(
    left_rows: list[dict[str, Any]],
    right_rows: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    pairs: list[dict[str, Any]] = []
    if right_rows is None:
        for left_index, left in enumerate(left_rows):
            for right in left_rows[left_index + 1 :]:
                distance = hamming(str(left["phash64"]), str(right["phash64"]))
                if distance <= PHASH_THRESHOLD:
                    pairs.append(
                        {
                            "left": left["filename"],
                            "right": right["filename"],
                            "hamming_distance": distance,
                        }
                    )
        return pairs

    for left in left_rows:
        for right in right_rows:
            distance = hamming(str(left["phash64"]), str(right["phash64"]))
            if distance <= PHASH_THRESHOLD:
                pairs.append(
                    {
                        "xinzhai_filename": left["filename"],
                        "rocole_path": right["path"],
                        "rocole_split": right["split"],
                        "hamming_distance": distance,
                    }
                )
    return pairs


def nearest_train_val(
    xinzhai_rows: list[dict[str, Any]], train_val_rows: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    nearest: list[dict[str, Any]] = []
    for xinzhai in xinzhai_rows:
        best = min(
            train_val_rows,
            key=lambda row: hamming(str(xinzhai["phash64"]), str(row["phash64"])),
        )
        nearest.append(
            {
                "xinzhai_filename": xinzhai["filename"],
                "nearest_rocole_path": best["path"],
                "rocole_split": best["split"],
                "hamming_distance": hamming(
                    str(xinzhai["phash64"]), str(best["phash64"])
                ),
            }
        )
    return nearest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--external-root", type=Path, required=True)
    parser.add_argument(
        "--manifest", type=Path, default=ROOT / "data" / "processed" / "manifest.csv"
    )
    parser.add_argument(
        "--output-dir", type=Path, default=ROOT / "reports" / "xinzhai_audit"
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    external_root = args.external_root.resolve()
    archive = external_root / "data.zip"
    data_root = external_root / "extracted" / "data"
    image_dir = data_root / "image"
    label_dir = data_root / "labels"
    manifest_path = args.manifest.resolve()
    output_dir = args.output_dir.resolve()

    archive_size = archive.stat().st_size
    archive_md5 = digest(archive, "md5")
    if archive_size != PUBLISHED_ARCHIVE_SIZE or archive_md5 != PUBLISHED_ARCHIVE_MD5:
        raise RuntimeError(
            f"El ZIP no coincide con Zenodo: {archive_size}, {archive_md5}"
        )

    class_names = read_classes(label_dir / "classes.txt")
    images = sorted(image_dir.glob("*.jpg"), key=lambda path: path.name.lower())
    labels = {
        path.stem: path
        for path in label_dir.glob("*.txt")
        if path.name.lower() != "classes.txt"
    }
    if len(images) != len(labels):
        raise RuntimeError(f"Imágenes/etiquetas no emparejadas: {len(images)}/{len(labels)}")

    inventory: list[dict[str, Any]] = []
    box_rows: list[dict[str, Any]] = []
    dimensions: Counter[str] = Counter()
    modes: Counter[str] = Counter()
    exif_counter: dict[str, Counter[str]] = defaultdict(Counter)
    timestamp_values: list[datetime] = []
    for index, image_path in enumerate(images, 1):
        label_path = labels.get(image_path.stem)
        if label_path is None:
            raise RuntimeError(f"Falta etiqueta para {image_path.name}")
        boxes = read_boxes(label_path, class_names)
        if not boxes:
            raise RuntimeError(f"Anotación vacía: {label_path.name}")
        with Image.open(image_path) as image:
            image.load()
            width, height = image.size
            image_mode = image.mode
            exif = exif_fields(image)
            perceptual = phash64(image)
        timestamp = filename_timestamp(image_path.stem)
        if timestamp is not None:
            timestamp_values.append(timestamp)
        dimensions[f"{width}x{height}"] += 1
        modes[image_mode] += 1
        for field, value in exif.items():
            exif_counter[field][value or "<missing>"] += 1

        class_ids = sorted({int(box["class_id"]) for box in boxes})
        present_names = [class_names[class_id] for class_id in class_ids]
        image_row = {
            "filename": image_path.name,
            "relative_image_path": f"data/image/{image_path.name}",
            "relative_label_path": f"data/labels/{label_path.name}",
            "sha256": digest(image_path),
            "phash64": perceptual,
            "width": width,
            "height": height,
            "mode": image_mode,
            "filename_timestamp": timestamp.isoformat() if timestamp else "",
            "exif_datetime": exif["DateTime"],
            "exif_datetime_original": exif["DateTimeOriginal"],
            "exif_make": exif["Make"],
            "exif_model": exif["Model"],
            "exif_software": exif["Software"],
            "box_count": len(boxes),
            "class_ids": ";".join(str(value) for value in class_ids),
            "class_names": ";".join(present_names),
            "class_count": len(class_ids),
            "is_multiclass": len(class_ids) > 1,
        }
        inventory.append(image_row)
        for box_index, box in enumerate(boxes, 1):
            box_rows.append(
                {
                    "filename": image_path.name,
                    "box_index": box_index,
                    **box,
                }
            )
        if index % 100 == 0 or index == len(images):
            print(f"Xinzhai: {index}/{len(images)}")

    with manifest_path.open(encoding="utf-8", newline="") as handle:
        manifest_reader = csv.DictReader(handle)
        train_val_manifest: list[dict[str, str]] = []
        test_hashes: set[str] = set()
        for row in manifest_reader:
            split = row["split"]
            if split == "test":
                # Del conjunto reservado solo se conserva el hash ya registrado.
                test_hashes.add(row["sha256"])
                continue
            if split not in {"train", "val"}:
                raise RuntimeError(f"Partición inesperada: {split}")
            train_val_manifest.append(
                {"path": row["path"], "split": split, "sha256": row["sha256"]}
            )

    train_val_phashes: list[dict[str, Any]] = []
    for index, row in enumerate(train_val_manifest, 1):
        image_path = ROOT / row["path"]
        with Image.open(image_path) as image:
            image.load()
            perceptual = phash64(image)
        train_val_phashes.append({**row, "phash64": perceptual})
        if index % 200 == 0 or index == len(train_val_manifest):
            print(f"RoCoLe TRAIN/VAL: {index}/{len(train_val_manifest)}")

    xinzhai_hashes = {str(row["sha256"]) for row in inventory}
    train_val_hashes = {row["sha256"] for row in train_val_manifest}
    exact_train_val = sorted(xinzhai_hashes & train_val_hashes)
    exact_test = sorted(xinzhai_hashes & test_hashes)
    exact_internal = same_hash_pairs(inventory)
    phash_internal = perceptual_pairs(inventory)
    phash_train_val = perceptual_pairs(inventory, train_val_phashes)
    nearest = nearest_train_val(inventory, train_val_phashes)

    image_class_counts: Counter[str] = Counter()
    class_set_counts: Counter[str] = Counter()
    box_class_counts: Counter[str] = Counter()
    for row in inventory:
        names = str(row["class_names"]).split(";")
        for name in names:
            image_class_counts[name] += 1
        class_set_counts[str(row["class_names"])] += 1
    for row in box_rows:
        box_class_counts[str(row["class_name"])] += 1

    filename_patterns = Counter()
    for image_path in images:
        stem = image_path.stem
        if re.fullmatch(r"IMG_\d{8}_\d{6}", stem):
            filename_patterns["IMG_YYYYMMDD_HHMMSS"] += 1
        elif re.fullmatch(r"IMG\d{14}", stem):
            filename_patterns["IMGYYYYMMDDHHMMSS"] += 1
        elif re.fullmatch(r"IMG\d{14}_\d+", stem):
            filename_patterns["IMGYYYYMMDDHHMMSS_suffix"] += 1
        elif re.fullmatch(r"IMG_\d{8}_\d{6}_edit_\d+", stem):
            filename_patterns["IMG_YYYYMMDD_HHMMSS_edit"] += 1
        else:
            filename_patterns["unparsed"] += 1

    summary: dict[str, Any] = {
        "scope": {
            "external_dataset_images_opened": len(inventory),
            "rocole_train_val_images_opened_for_phash": len(train_val_phashes),
            "rocole_test_images_opened": 0,
            "rocole_test_labels_or_predictions_consulted": False,
            "rocole_test_sha256_values_used": len(test_hashes),
        },
        "source": {
            "zenodo_record": 21442135,
            "doi": "10.5281/zenodo.21442135",
            "license": "CC BY 4.0",
            "archive_name": archive.name,
            "archive_size": archive_size,
            "archive_md5": archive_md5,
            "archive_matches_published_size_and_md5": True,
        },
        "inventory": {
            "images": len(inventory),
            "annotation_files": len(labels),
            "classes_file": "data/labels/classes.txt",
            "classes": class_names,
            "red_spider_mite_class_present": any(
                "mite" in name.casefold() or "spider" in name.casefold()
                for name in class_names
            ),
            "boxes": len(box_rows),
            "multiclass_images": sum(bool(row["is_multiclass"]) for row in inventory),
            "single_class_images": sum(not bool(row["is_multiclass"]) for row in inventory),
            "images_by_class": dict(image_class_counts),
            "boxes_by_class": dict(box_class_counts),
            "class_sets": dict(class_set_counts),
            "dimensions": dict(dimensions),
            "modes": dict(modes),
            "filename_patterns": dict(filename_patterns),
            "filename_timestamp_min": min(timestamp_values).isoformat() if timestamp_values else None,
            "filename_timestamp_max": max(timestamp_values).isoformat() if timestamp_values else None,
            "filename_timestamps_parsed": len(timestamp_values),
            "exif": {field: dict(values) for field, values in exif_counter.items()},
        },
        "duplicates": {
            "exact_pairs_within_xinzhai": len(exact_internal),
            "perceptual_candidate_pairs_within_xinzhai_hamming_lte_4": len(phash_internal),
            "exact_sha256_matches_rocole_train_val": len(exact_train_val),
            "exact_sha256_matches_rocole_test_hash_registry": len(exact_test),
            "perceptual_candidates_rocole_train_val_hamming_lte_4": len(phash_train_val),
            "minimum_nearest_rocole_train_val_hamming": min(
                int(row["hamming_distance"]) for row in nearest
            ),
            "sha256_limitation": (
                "No exact match does not rule out resized, recompressed, cropped or otherwise recoded copies."
            ),
            "phash_limitation": (
                "A perceptual-hash candidate is a screening signal, not proof of biological identity or provenance."
            ),
        },
    }

    inventory_fields = list(inventory[0].keys())
    write_csv(output_dir / "image_inventory.csv", inventory, inventory_fields)
    write_csv(
        output_dir / "boxes.csv",
        box_rows,
        ["filename", "box_index", "class_id", "class_name", "x_center", "y_center", "width", "height"],
    )
    write_csv(
        output_dir / "exact_duplicates_within_xinzhai.csv",
        exact_internal,
        ["sha256", "first", "second"],
    )
    write_csv(
        output_dir / "phash_candidates_within_xinzhai.csv",
        phash_internal,
        ["left", "right", "hamming_distance"],
    )
    write_csv(
        output_dir / "phash_candidates_rocole_train_val.csv",
        phash_train_val,
        ["xinzhai_filename", "rocole_path", "rocole_split", "hamming_distance"],
    )
    write_csv(
        output_dir / "nearest_rocole_train_val_phash.csv",
        nearest,
        ["xinzhai_filename", "nearest_rocole_path", "rocole_split", "hamming_distance"],
    )
    write_json(output_dir / "audit_summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
