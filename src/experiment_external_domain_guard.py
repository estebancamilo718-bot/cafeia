from __future__ import annotations

"""Experimento no integrado de ampliacion del filtro de dominio.

El script compara el filtro activo con un candidato que conserva exactamente
el extractor, los cinco vecinos (o el valor guardado en el control) y el
umbral del control, pero agrega referencias externas auditadas de CoffeeLeaf-
CO. No entrena, no consulta imagenes de TEST de RoCoLe y nunca escribe en
``data/`` ni en ``models/``.

La estructura publica de CoffeeLeaf-CO puede cambiar. Por eso no se infieren
columnas ni decisiones por el nombre de archivo: el manifiesto de procedencia
debe declarar de forma explicita la fuente, la elegibilidad para el filtro y
el SHA256 de cada imagen. Ante una estructura desconocida se falla con un
mensaje que enumera las columnas admitidas.
"""

import argparse
import csv
import hashlib
import io
import json
import math
import platform
import re
import sys
import time
import unicodedata
import zipfile
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Sequence

import torch
from PIL import Image, ImageOps, UnidentifiedImageError

from src.common import ROOT, load_checkpoint, transform
from src.domain_guard import DomainGuard, extract_mobilenet_embedding


EXPECTED_CLASSES = [
    "coffee___healthy",
    "coffee___red_spider_mite",
    "coffee___rust",
]
TRUE_VALUES = {
    "1",
    "true",
    "yes",
    "si",
    "include",
    "included",
    "eligible",
    "approved",
    "aprobado",
}
FALSE_VALUES = {
    "0",
    "false",
    "no",
    "exclude",
    "excluded",
    "ineligible",
    "rejected",
    "rechazado",
}
PATH_COLUMNS = (
    "path",
    "relative_path",
    "image_path",
    "archive_path",
    "filename",
    "file_name",
    "image_filename",
)
SOURCE_COLUMNS = (
    "source",
    "source_id",
    "source_group",
    "source_name",
    "origin",
    "origin_source",
)
GUARD_DECISION_COLUMNS = (
    "eligible_for_domain_guard",
    "domain_guard_eligible",
    "include_in_domain_guard",
    "guard_decision",
)
SHA256_COLUMNS = ("sha256", "image_sha256", "file_sha256")
MD5_COLUMNS = ("md5", "image_md5", "file_md5")
LABEL_COLUMNS = ("label", "category", "detail", "original_label")
DEFAULT_OWN_SOURCE_VALUES = (
    "1",
    "Source 1",
    "source_1",
    "source1",
    "own-field",
    "own_field",
    "own field",
    "source 1 own field",
    "own field capture",
    "own capture",
    "self captured",
    "captura propia",
    "capturas propias",
)


@dataclass(frozen=True)
class AssetRecord:
    dataset: str
    path: str
    sha256: str
    md5: str | None
    source: str
    label: str
    used_as_reference: bool


class ByteStore:
    """Lectura controlada desde un directorio o desde un ZIP, sin extraer."""

    def __init__(self, source: Path) -> None:
        self.source = source.resolve()
        self.kind: str
        self._zip: zipfile.ZipFile | None = None
        self._zip_members: set[str] = set()
        if self.source.is_dir():
            self.kind = "directory"
        elif self.source.is_file() and zipfile.is_zipfile(self.source):
            self.kind = "zip"
            self._zip = zipfile.ZipFile(self.source)
            members = [info.filename for info in self._zip.infolist() if not info.is_dir()]
            duplicates = sorted(name for name, count in Counter(members).items() if count > 1)
            if duplicates:
                raise ValueError(
                    "El ZIP contiene nombres de miembro duplicados; no es seguro resolverlos: "
                    + ", ".join(duplicates[:5])
                )
            encrypted = [info.filename for info in self._zip.infolist() if info.flag_bits & 0x1]
            if encrypted:
                raise ValueError(
                    "El ZIP contiene miembros cifrados no admitidos: "
                    + ", ".join(encrypted[:5])
                )
            self._zip_members = set(members)
        else:
            raise ValueError(
                f"La fuente externa debe ser un directorio o un ZIP valido: {source}"
            )

    def close(self) -> None:
        if self._zip is not None:
            self._zip.close()

    def __enter__(self) -> ByteStore:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def read(self, raw_path: str) -> bytes:
        relative = safe_relative_path(raw_path)
        portable = relative.as_posix()
        if self.kind == "zip":
            if portable not in self._zip_members:
                raise FileNotFoundError(
                    f"El miembro '{portable}' no existe exactamente en el ZIP. "
                    "No se adivinan prefijos ni nombres por basename."
                )
            assert self._zip is not None
            return self._zip.read(portable)

        target = (self.source / Path(*relative.parts)).resolve()
        if not target.is_relative_to(self.source):
            raise ValueError(f"La ruta sale del directorio autorizado: {raw_path}")
        if not target.is_file():
            raise FileNotFoundError(f"No se encontro el archivo auditado: {target}")
        return target.read_bytes()


def normalized_token(value: str) -> str:
    ascii_value = "".join(
        character
        for character in unicodedata.normalize("NFKD", value)
        if not unicodedata.combining(character)
    )
    return re.sub(r"[^a-z0-9]+", "", ascii_value.casefold())


def normalized_header(value: str) -> str:
    ascii_value = "".join(
        character
        for character in unicodedata.normalize("NFKD", value)
        if not unicodedata.combining(character)
    )
    return re.sub(r"[^a-z0-9]+", "_", ascii_value.casefold()).strip("_")


def safe_relative_path(raw_path: str) -> PurePosixPath:
    value = raw_path.strip().replace("\\", "/")
    path = PurePosixPath(value)
    if not value or path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError(f"Ruta relativa no valida en el manifiesto: {raw_path!r}")
    return path


def sha256_file(path: Path) -> str:
    return digest_file(path, "sha256")


def digest_file(path: Path, algorithm: str) -> str:
    digest = hashlib.new(algorithm)
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_digest(value: str, algorithm: str, context: str) -> str:
    normalized = value.strip().lower()
    expected_length = hashlib.new(algorithm).digest_size * 2
    if len(normalized) != expected_length or any(c not in "0123456789abcdef" for c in normalized):
        raise ValueError(
            f"{context} debe ser un {algorithm.upper()} hexadecimal de {expected_length} caracteres"
        )
    return normalized


def verify_file_digest(path: Path, expected: str, algorithm: str, context: str) -> str:
    expected_normalized = validate_digest(expected, algorithm, context)
    actual = digest_file(path, algorithm)
    if actual != expected_normalized:
        raise RuntimeError(
            f"{context} no coincide: esperado {expected_normalized}, obtenido {actual}"
        )
    return actual


def load_manifest(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    if not path.is_file():
        raise FileNotFoundError(f"No existe el manifiesto: {path}")
    suffix = path.suffix.casefold()
    if suffix == ".csv":
        with path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if not reader.fieldnames:
                raise ValueError(f"El CSV no contiene encabezados: {path}")
            rows = [
                {str(key): "" if value is None else str(value) for key, value in row.items()}
                for row in reader
            ]
            headers = [str(name) for name in reader.fieldnames]
    elif suffix == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            payload = payload.get("rows")
        if not isinstance(payload, list) or not all(isinstance(item, dict) for item in payload):
            raise ValueError(
                f"El JSON debe ser una lista de objetos o un objeto con la clave 'rows': {path}"
            )
        rows = [
            {str(key): "" if value is None else str(value) for key, value in item.items()}
            for item in payload
        ]
        headers = sorted({key for row in rows for key in row})
    else:
        raise ValueError(f"Solo se admiten manifiestos CSV o JSON: {path}")
    if not rows:
        raise ValueError(f"El manifiesto esta vacio: {path}")
    return rows, headers


def resolve_column(
    headers: Sequence[str],
    aliases: Sequence[str],
    *,
    context: str,
    required: bool = True,
) -> str | None:
    by_normalized: dict[str, list[str]] = defaultdict(list)
    for header in headers:
        by_normalized[normalized_header(header)].append(header)
    matches: list[str] = []
    for alias in aliases:
        matches.extend(by_normalized.get(normalized_header(alias), []))
    matches = list(dict.fromkeys(matches))
    if len(matches) > 1:
        raise ValueError(
            f"{context}: hay columnas ambiguas para {aliases}: {matches}. Conserva solo una."
        )
    if not matches:
        if required:
            raise ValueError(
                f"{context}: falta una columna requerida. Se admite una de: {', '.join(aliases)}. "
                f"Columnas encontradas: {', '.join(headers)}"
            )
        return None
    return matches[0]


def choose_optional_column(
    headers: Sequence[str],
    aliases_in_priority_order: Sequence[str],
    *,
    context: str,
) -> str | None:
    """Elige la primera columna disponible sin confundir campos coexistentes.

    Algunos manifiestos contienen a la vez ``category`` y ``detail``. Eso no
    es ambiguo para un campo descriptivo opcional: se usa la prioridad
    declarada. Dos encabezados que normalicen al mismo alias si son ambiguos.
    """

    by_normalized: dict[str, list[str]] = defaultdict(list)
    for header in headers:
        by_normalized[normalized_header(header)].append(header)
    for alias in aliases_in_priority_order:
        matches = by_normalized.get(normalized_header(alias), [])
        if len(matches) > 1:
            raise ValueError(
                f"{context}: hay encabezados duplicados para {alias!r}: {matches}"
            )
        if matches:
            return matches[0]
    return None


def parse_explicit_decision(value: str, context: str) -> bool:
    token = normalized_token(value)
    if token in {normalized_token(item) for item in TRUE_VALUES}:
        return True
    if token in {normalized_token(item) for item in FALSE_VALUES}:
        return False
    raise ValueError(
        f"{context}: decision de elegibilidad ambigua {value!r}. "
        "Usa true/false, included/excluded o eligible/ineligible."
    )


def load_coffeeleaf_records(
    manifest_path: Path,
    own_source_values: Sequence[str],
) -> tuple[list[AssetRecord], dict[str, Any]]:
    rows, headers = load_manifest(manifest_path)
    path_column = resolve_column(headers, PATH_COLUMNS, context="provenance_manifest")
    source_column = resolve_column(headers, SOURCE_COLUMNS, context="provenance_manifest")
    decision_column = resolve_column(
        headers,
        GUARD_DECISION_COLUMNS,
        context="provenance_manifest",
    )
    sha_column = resolve_column(headers, SHA256_COLUMNS, context="provenance_manifest")
    md5_column = resolve_column(
        headers,
        MD5_COLUMNS,
        context="provenance_manifest",
        required=False,
    )
    label_column = choose_optional_column(
        headers,
        LABEL_COLUMNS,
        context="provenance_manifest",
    )
    allowed_sources = {normalized_token(value) for value in own_source_values}
    if not allowed_sources:
        raise ValueError("Debe definirse al menos un valor permitido para Source 1/own-field")

    selected: list[AssetRecord] = []
    source_counts: Counter[str] = Counter()
    excluded_counts: Counter[str] = Counter()
    for line_number, row in enumerate(rows, start=2):
        raw_source = row[source_column].strip()
        source_counts[raw_source or "<vacio>"] += 1
        if normalized_token(raw_source) not in allowed_sources:
            excluded_counts["not_source_1_own_field"] += 1
            continue
        if not parse_explicit_decision(
            row[decision_column],
            f"provenance_manifest linea {line_number}",
        ):
            excluded_counts["audit_marked_ineligible"] += 1
            continue
        relative_path = safe_relative_path(row[path_column]).as_posix()
        sha256 = validate_digest(
            row[sha_column],
            "sha256",
            f"provenance_manifest linea {line_number} SHA256",
        )
        md5 = (
            validate_digest(
                row[md5_column],
                "md5",
                f"provenance_manifest linea {line_number} MD5",
            )
            if md5_column and row[md5_column].strip()
            else None
        )
        selected.append(
            AssetRecord(
                dataset="coffeeleaf_co_reference",
                path=relative_path,
                sha256=sha256,
                md5=md5,
                source=raw_source,
                label=row[label_column].strip() if label_column else "",
                used_as_reference=True,
            )
        )

    if not selected:
        raise ValueError(
            "provenance_manifest no contiene filas elegibles cuyo valor de source coincida "
            "exactamente con Source 1/own-field. Valores encontrados: "
            + ", ".join(sorted(source_counts))
        )
    duplicate_paths = sorted(
        path for path, count in Counter(record.path for record in selected).items() if count > 1
    )
    duplicate_hashes = sorted(
        digest for digest, count in Counter(record.sha256 for record in selected).items() if count > 1
    )
    if duplicate_paths or duplicate_hashes:
        raise ValueError(
            "El subconjunto elegible contiene duplicados exactos. La auditoria debe resolverlos "
            f"antes del experimento. Rutas duplicadas: {duplicate_paths[:5]}; "
            f"SHA256 duplicados: {duplicate_hashes[:5]}"
        )
    return selected, {
        "manifest_row_count": len(rows),
        "eligible_reference_count": len(selected),
        "source_value_counts": dict(sorted(source_counts.items())),
        "excluded_counts": dict(sorted(excluded_counts.items())),
        "accepted_source_tokens": sorted(allowed_sources),
        "resolved_columns": {
            "path": path_column,
            "source": source_column,
            "guard_decision": decision_column,
            "sha256": sha_column,
            "md5": md5_column,
            "label": label_column,
        },
    }


def load_local_records(
    manifest_path: Path,
    *,
    dataset: str,
    root: Path,
    expected_negative: bool,
) -> list[AssetRecord]:
    rows, headers = load_manifest(manifest_path)
    path_column = resolve_column(headers, PATH_COLUMNS, context=dataset)
    sha_column = resolve_column(headers, SHA256_COLUMNS, context=dataset)
    source_column = resolve_column(headers, SOURCE_COLUMNS, context=dataset)
    label_column = choose_optional_column(
        headers,
        ("detail", "label", "original_label", "category"),
        context=dataset,
    )
    md5_column = resolve_column(
        headers,
        MD5_COLUMNS,
        context=dataset,
        required=False,
    )
    category_column = resolve_column(
        headers,
        ("category", "kind", "target_type"),
        context=dataset,
        required=expected_negative,
    )
    records: list[AssetRecord] = []
    for line_number, row in enumerate(rows, start=2):
        if expected_negative:
            category = row[category_column].strip() if category_column else ""
            if not normalized_token(category).startswith("non"):
                raise ValueError(
                    f"{dataset} linea {line_number}: la categoria {category!r} no declara "
                    "explicitamente un negativo (se esperaba un valor que empiece por 'non_')."
                )
        raw_path = safe_relative_path(row[path_column]).as_posix()
        # Se valida aqui para no permitir rutas absolutas aun cuando root sea externo.
        target = (root.resolve() / Path(*PurePosixPath(raw_path).parts)).resolve()
        if not target.is_relative_to(root.resolve()):
            raise ValueError(f"{dataset}: la ruta sale del directorio autorizado: {raw_path}")
        source = row[source_column].strip()
        detail = row[label_column].strip() if label_column else ""
        records.append(
            AssetRecord(
                dataset=dataset,
                path=raw_path,
                sha256=validate_digest(
                    row[sha_column],
                    "sha256",
                    f"{dataset} linea {line_number} SHA256",
                ),
                md5=(
                    validate_digest(
                        row[md5_column],
                        "md5",
                        f"{dataset} linea {line_number} MD5",
                    )
                    if md5_column and row[md5_column].strip()
                    else None
                ),
                source=source,
                label=f"{source}:{detail}" if detail else source,
                used_as_reference=False,
            )
        )
    if not records:
        raise ValueError(f"{dataset}: no hay filas para evaluar")
    duplicate_paths = [path for path, count in Counter(r.path for r in records).items() if count > 1]
    duplicate_hashes = [sha for sha, count in Counter(r.sha256 for r in records).items() if count > 1]
    if duplicate_paths or duplicate_hashes:
        raise ValueError(
            f"{dataset}: el manifiesto contiene rutas o SHA256 duplicados; "
            "debe fijar observaciones unicas antes de evaluar"
        )
    return records


def verify_records(
    records: Sequence[AssetRecord],
    reader: Callable[[str], bytes],
    *,
    context: str,
) -> dict[str, Any]:
    aggregate_sha256 = hashlib.sha256()
    aggregate_md5 = hashlib.md5(usedforsecurity=False)
    total_bytes = 0
    formats: Counter[str] = Counter()
    for index, record in enumerate(records, start=1):
        payload = reader(record.path)
        actual_sha256 = hashlib.sha256(payload).hexdigest()
        actual_md5 = hashlib.md5(payload, usedforsecurity=False).hexdigest()
        if actual_sha256 != record.sha256:
            raise RuntimeError(
                f"{context} registro {index} ({record.path}): SHA256 no coincide; "
                f"esperado {record.sha256}, obtenido {actual_sha256}"
            )
        if record.md5 is not None and actual_md5 != record.md5:
            raise RuntimeError(
                f"{context} registro {index} ({record.path}): MD5 no coincide; "
                f"esperado {record.md5}, obtenido {actual_md5}"
            )
        try:
            with Image.open(io.BytesIO(payload)) as image:
                image.verify()
                image_format = image.format or "unknown"
        except (UnidentifiedImageError, OSError, SyntaxError, ValueError) as exc:
            raise ValueError(f"{context}: imagen no valida {record.path}: {exc}") from exc
        formats[image_format] += 1
        total_bytes += len(payload)
        material = f"{record.path}\0{actual_sha256}\0{actual_md5}\n".encode("utf-8")
        aggregate_sha256.update(material)
        aggregate_md5.update(material)
    return {
        "count": len(records),
        "total_bytes": total_bytes,
        "formats": dict(sorted(formats.items())),
        "selection_sha256": aggregate_sha256.hexdigest(),
        "selection_md5": aggregate_md5.hexdigest(),
        "per_file_sha256_verified": True,
        "per_file_md5_verified_when_declared": True,
    }


def decode_for_model(payload: bytes, context: str) -> torch.Tensor:
    try:
        with Image.open(io.BytesIO(payload)) as image:
            image.load()
            rgb = ImageOps.exif_transpose(image).convert("RGB")
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError) as exc:
        raise ValueError(f"No se pudo decodificar {context}: {exc}") from exc
    return transform(training=False)(rgb)


def embeddings_for_records(
    model: torch.nn.Module,
    records: Sequence[AssetRecord],
    reader: Callable[[str], bytes],
    batch_size: int,
) -> torch.Tensor:
    if not records:
        raise ValueError("No hay registros para extraer embeddings")
    chunks: list[torch.Tensor] = []
    tensors: list[torch.Tensor] = []
    with torch.inference_mode():
        for record in records:
            tensors.append(decode_for_model(reader(record.path), record.path))
            if len(tensors) == batch_size:
                chunks.append(extract_mobilenet_embedding(model, torch.stack(tensors)).cpu())
                tensors.clear()
        if tensors:
            chunks.append(extract_mobilenet_embedding(model, torch.stack(tensors)).cpu())
    result = torch.cat(chunks)
    if result.shape[0] != len(records) or not torch.isfinite(result).all():
        raise RuntimeError("Los embeddings externos son incompletos o contienen valores no finitos")
    return result


def split_validation_groups(
    rows: list[dict[str, str]], seed: int
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    groups = sorted({row["group"] for row in rows})
    ranked = sorted(
        groups,
        key=lambda group: hashlib.sha256(f"{seed}:{group}".encode()).hexdigest(),
    )
    calibration_groups = set(ranked[::2])
    calibration = [row for row in rows if row["group"] in calibration_groups]
    evaluation = [row for row in rows if row["group"] not in calibration_groups]
    if not calibration or not evaluation:
        raise RuntimeError("No fue posible reproducir la separacion de VAL por grupos")
    if {row["group"] for row in calibration} & {row["group"] for row in evaluation}:
        raise RuntimeError("La separacion reproducida comparte grupos")
    return calibration, evaluation


def rocole_evaluation_records(
    manifest_path: Path,
    seed: int,
) -> tuple[list[AssetRecord], set[str], set[str], dict[str, int]]:
    rows, headers = load_manifest(manifest_path)
    required = {"path", "label", "group", "sha256", "split"}
    missing = sorted(required - set(headers))
    if missing:
        raise ValueError(f"El manifiesto RoCoLe carece de columnas: {missing}")
    # Los hashes de TEST se usan solo como lista de exclusion. No se abren rutas,
    # no se leen etiquetas y no se calculan predicciones de esas filas.
    test_hashes = {
        validate_digest(row["sha256"], "sha256", "SHA256 TEST registrado")
        for row in rows
        if row["split"] == "test"
    }
    non_test_hashes = {
        validate_digest(row["sha256"], "sha256", "SHA256 RoCoLe registrado")
        for row in rows
        if row["split"] != "test"
    }
    val_rows = [row for row in rows if row["split"] == "val"]
    _, evaluation_rows = split_validation_groups(val_rows, seed)
    records = [
        AssetRecord(
            dataset="rocole_val_evaluation",
            path=safe_relative_path(row["path"]).as_posix(),
            sha256=validate_digest(row["sha256"], "sha256", "SHA256 VAL"),
            md5=None,
            source="RoCoLe VAL evaluation",
            label=row["label"],
            used_as_reference=False,
        )
        for row in evaluation_rows
    ]
    counts = dict(sorted(Counter(record.label for record in records).items()))
    return records, test_hashes, non_test_hashes, counts


def ensure_no_overlap(
    records: Sequence[AssetRecord],
    forbidden_hashes: set[str],
    context: str,
) -> None:
    collisions = sorted({record.sha256 for record in records} & forbidden_hashes)
    if collisions:
        raise RuntimeError(
            f"{context} contiene {len(collisions)} SHA256 prohibidos. "
            "La auditoria debe marcarlos como excluidos antes de ejecutar. "
            f"Primeros hashes: {collisions[:5]}"
        )


def wilson_interval(successes: int, total: int, z: float = 1.959963984540054) -> list[float]:
    if total <= 0:
        raise ValueError("Wilson requiere al menos una observacion")
    proportion = successes / total
    denominator = 1.0 + z * z / total
    center = (proportion + z * z / (2.0 * total)) / denominator
    margin = (
        z
        * math.sqrt(
            proportion * (1.0 - proportion) / total
            + z * z / (4.0 * total * total)
        )
        / denominator
    )
    return [max(0.0, center - margin), min(1.0, center + margin)]


def distribution(values: Sequence[float]) -> dict[str, float]:
    ordered = sorted(values)
    if not ordered:
        raise ValueError("No hay scores para resumir")

    def quantile(q: float) -> float:
        position = q * (len(ordered) - 1)
        lower = math.floor(position)
        upper = math.ceil(position)
        if lower == upper:
            return ordered[lower]
        fraction = position - lower
        return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction

    return {
        "min": ordered[0],
        "q25": quantile(0.25),
        "median": quantile(0.50),
        "q75": quantile(0.75),
        "max": ordered[-1],
    }


def comparison_metrics(
    records: Sequence[AssetRecord],
    control_scores: Sequence[float],
    candidate_scores: Sequence[float],
    threshold: float,
    *,
    positive: bool,
) -> dict[str, Any]:
    if not (len(records) == len(control_scores) == len(candidate_scores)):
        raise ValueError("Cantidad inconsistente de registros y scores")
    control = [score >= threshold for score in control_scores]
    candidate = [score >= threshold for score in candidate_scores]

    def one(values: Sequence[bool], scores: Sequence[float]) -> dict[str, Any]:
        accepted = sum(values)
        rejected = len(values) - accepted
        successes = accepted if positive else rejected
        return {
            "count": len(values),
            "accepted": accepted,
            "rejected": rejected,
            "acceptance_rate": accepted / len(values),
            "rejection_rate": rejected / len(values),
            "target_rate_name": "coffee_recall" if positive else "negative_specificity",
            "target_rate": successes / len(values),
            "target_rate_wilson_95": wilson_interval(successes, len(values)),
            "score_distribution": distribution(scores),
        }

    groups: dict[str, list[int]] = defaultdict(list)
    for index, record in enumerate(records):
        key = record.label or record.source
        groups[key].append(index)
    per_group: dict[str, Any] = {}
    for key, indices in sorted(groups.items()):
        per_group[key] = {
            "control": one(
                [control[index] for index in indices],
                [control_scores[index] for index in indices],
            ),
            "candidate": one(
                [candidate[index] for index in indices],
                [candidate_scores[index] for index in indices],
            ),
        }
    return {
        "expected": "coffee_positive" if positive else "known_negative",
        "threshold_fixed": threshold,
        "control": one(control, control_scores),
        "candidate": one(candidate, candidate_scores),
        "paired": {
            "both_accepted": sum(a and b for a, b in zip(control, candidate, strict=True)),
            "control_only_accepted": sum(a and not b for a, b in zip(control, candidate, strict=True)),
            "candidate_only_accepted": sum(not a and b for a, b in zip(control, candidate, strict=True)),
            "both_rejected": sum(not a and not b for a, b in zip(control, candidate, strict=True)),
            "acceptance_rate_delta_candidate_minus_control": (
                sum(candidate) - sum(control)
            )
            / len(records),
        },
        "per_group": per_group,
    }


def prediction_rows(
    records: Sequence[AssetRecord],
    control_scores: Sequence[float],
    candidate_scores: Sequence[float],
    threshold: float,
) -> list[dict[str, Any]]:
    return [
        {
            "dataset": record.dataset,
            "path": record.path,
            "source": record.source,
            "label_or_detail": record.label,
            "sha256": record.sha256,
            "used_as_candidate_reference": record.used_as_reference,
            "control_domain_score": control_score,
            "control_accepted": control_score >= threshold,
            "candidate_domain_score": candidate_score,
            "candidate_accepted": candidate_score >= threshold,
            "fixed_threshold": threshold,
        }
        for record, control_score, candidate_score in zip(
            records, control_scores, candidate_scores, strict=True
        )
    ]


def scores_for_pair(
    control: DomainGuard,
    candidate: DomainGuard,
    embeddings: torch.Tensor,
) -> tuple[list[float], list[float]]:
    with torch.inference_mode():
        return control.scores(embeddings).tolist(), candidate.scores(embeddings).tolist()


def write_csv(path: Path, rows: Sequence[dict[str, Any]]) -> None:
    if not rows:
        return
    with path.open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def check_output_path(output_dir: Path) -> Path:
    resolved = output_dir.resolve()
    if output_dir.exists():
        raise FileExistsError(
            f"El directorio de salida ya existe y no se sobrescribira: {output_dir}"
        )
    for forbidden in (ROOT / "data", ROOT / "models"):
        forbidden_resolved = forbidden.resolve()
        if resolved == forbidden_resolved or resolved.is_relative_to(forbidden_resolved):
            raise ValueError(
                f"La salida experimental no puede estar dentro de {forbidden_resolved}"
            )
    return resolved


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Compara el guard activo con un candidato que agrega referencias auditadas "
            "de CoffeeLeaf-CO. No entrena ni consulta TEST RoCoLe."
        )
    )
    parser.add_argument("--coffeeleaf-source", type=Path, required=True)
    parser.add_argument("--provenance-manifest", type=Path, required=True)
    parser.add_argument("--provenance-manifest-sha256", required=True)
    parser.add_argument(
        "--own-source-value",
        action="append",
        dest="own_source_values",
        help=(
            "Valor exacto (normalizado) que identifica Source 1/own-field. "
            "Puede repetirse; si se omite se usan alias conservadores."
        ),
    )
    parser.add_argument(
        "--source-md5",
        help="MD5 publicado del ZIP; obligatorio cuando --coffeeleaf-source es ZIP",
    )
    parser.add_argument(
        "--source-sha256",
        help="SHA256 fijado localmente del ZIP; obligatorio cuando la fuente es ZIP",
    )
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--checkpoint-sha256", required=True)
    parser.add_argument("--control-guard", type=Path, required=True)
    parser.add_argument("--control-guard-sha256", required=True)
    parser.add_argument(
        "--rocole-manifest",
        type=Path,
        default=ROOT / "data" / "processed" / "manifest.csv",
    )
    parser.add_argument("--ood-manifest", type=Path, required=True)
    parser.add_argument("--ood-manifest-sha256", required=True)
    parser.add_argument(
        "--ood-root",
        type=Path,
        default=ROOT,
        help="Raiz para las rutas relativas del manifiesto OOD",
    )
    parser.add_argument("--external-positive-manifest", type=Path)
    parser.add_argument("--external-positive-manifest-sha256")
    parser.add_argument("--external-positive-root", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--batch-size", type=int, default=16)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    started = time.perf_counter()
    if args.batch_size < 1:
        raise ValueError("--batch-size debe ser positivo")
    output_dir = check_output_path(args.output_dir)

    checkpoint_path = args.checkpoint.resolve()
    guard_path = args.control_guard.resolve()
    rocole_manifest_path = args.rocole_manifest.resolve()
    provenance_manifest_path = args.provenance_manifest.resolve()
    ood_manifest_path = args.ood_manifest.resolve()
    checkpoint_sha256 = verify_file_digest(
        checkpoint_path,
        args.checkpoint_sha256,
        "sha256",
        "checkpoint activo",
    )
    guard_sha256 = verify_file_digest(
        guard_path,
        args.control_guard_sha256,
        "sha256",
        "guard control",
    )
    provenance_manifest_sha256 = verify_file_digest(
        provenance_manifest_path,
        args.provenance_manifest_sha256,
        "sha256",
        "provenance_manifest",
    )
    ood_manifest_sha256 = verify_file_digest(
        ood_manifest_path,
        args.ood_manifest_sha256,
        "sha256",
        "manifiesto OOD",
    )

    coffeeleaf_source = args.coffeeleaf_source.resolve()
    if coffeeleaf_source.is_file() and not zipfile.is_zipfile(coffeeleaf_source):
        raise ValueError(
            f"--coffeeleaf-source es un archivo, pero no es un ZIP valido: {coffeeleaf_source}"
        )
    source_container: dict[str, Any] = {
        "name": coffeeleaf_source.name,
        "kind": "directory" if coffeeleaf_source.is_dir() else "zip",
    }
    if coffeeleaf_source.is_file():
        if not args.source_md5 or not args.source_sha256:
            raise ValueError(
                "Para un ZIP se requieren --source-md5 y --source-sha256; "
                "no se continua con una descarga no verificada."
            )
        source_container.update(
            {
                "size_bytes": coffeeleaf_source.stat().st_size,
                "md5": verify_file_digest(
                    coffeeleaf_source, args.source_md5, "md5", "ZIP CoffeeLeaf-CO"
                ),
                "sha256": verify_file_digest(
                    coffeeleaf_source,
                    args.source_sha256,
                    "sha256",
                    "ZIP CoffeeLeaf-CO",
                ),
            }
        )
    elif args.source_md5 or args.source_sha256:
        raise ValueError(
            "--source-md5/--source-sha256 describen el contenedor ZIP y no se "
            "aplican a un directorio extraido. Los archivos del directorio se "
            "verifican individualmente contra provenance_manifest."
        )

    control = DomainGuard.load(guard_path)
    model, checkpoint = load_checkpoint(checkpoint_path)
    if checkpoint.get("model") != "mobilenet":
        raise ValueError("El checkpoint activo no es MobileNet")
    classes = list(checkpoint.get("classes", []))
    if classes != EXPECTED_CLASSES:
        raise ValueError(f"Orden de clases inesperado: {classes}")
    if control.metadata.get("checkpoint_sha256") != checkpoint_sha256:
        raise RuntimeError("El guard control fue construido con otro checkpoint")
    if control.metadata.get("classes") != classes:
        raise RuntimeError("El guard control y el checkpoint no comparten el orden de clases")
    rocole_manifest_sha256 = sha256_file(rocole_manifest_path)
    if control.metadata.get("manifest_sha256") != rocole_manifest_sha256:
        raise RuntimeError("El guard control no corresponde al manifiesto RoCoLe vigente")
    if checkpoint.get("manifest_sha256") != rocole_manifest_sha256:
        raise RuntimeError("El checkpoint no corresponde al manifiesto RoCoLe vigente")
    seed = int(control.metadata.get("seed", 42))
    rocole_records, test_hashes, non_test_hashes, rocole_counts = rocole_evaluation_records(
        rocole_manifest_path,
        seed,
    )

    own_source_values = args.own_source_values or list(DEFAULT_OWN_SOURCE_VALUES)
    coffeeleaf_records, coffeeleaf_audit = load_coffeeleaf_records(
        provenance_manifest_path,
        own_source_values,
    )
    ensure_no_overlap(
        coffeeleaf_records,
        test_hashes,
        "Las referencias CoffeeLeaf-CO (colision con TEST RoCoLe)",
    )
    ensure_no_overlap(
        coffeeleaf_records,
        non_test_hashes,
        "Las referencias CoffeeLeaf-CO (colision con RoCoLe TRAIN/VAL)",
    )

    ood_root = args.ood_root.resolve()
    if not ood_root.is_dir():
        raise ValueError(f"--ood-root no es un directorio: {ood_root}")
    ood_records = load_local_records(
        ood_manifest_path,
        dataset="known_ood_negatives",
        root=ood_root,
        expected_negative=True,
    )
    ensure_no_overlap(ood_records, test_hashes, "El benchmark OOD")
    ensure_no_overlap(
        coffeeleaf_records,
        {record.sha256 for record in ood_records},
        "Las referencias CoffeeLeaf-CO (colision con el benchmark OOD)",
    )

    local_reader = ByteStore(ROOT)
    ood_reader = ByteStore(ood_root)
    try:
        rocole_verification = verify_records(
            rocole_records,
            local_reader.read,
            context="RoCoLe VAL evaluation",
        )
        ood_verification = verify_records(
            ood_records,
            ood_reader.read,
            context="benchmark OOD",
        )
        with ByteStore(coffeeleaf_source) as coffeeleaf_reader:
            coffeeleaf_verification = verify_records(
                coffeeleaf_records,
                coffeeleaf_reader.read,
                context="CoffeeLeaf-CO Source 1/own-field",
            )
            coffeeleaf_embeddings = embeddings_for_records(
                model,
                coffeeleaf_records,
                coffeeleaf_reader.read,
                args.batch_size,
            )

        candidate_references = torch.cat(
            [control.reference_embeddings.cpu(), coffeeleaf_embeddings.cpu()],
            dim=0,
        )
        candidate_metadata = {
            **control.metadata,
            "experiment_status": "candidate_not_integrated",
            "experiment_script": "src/experiment_external_domain_guard.py",
            "intervention": "add_audited_coffeeleaf_co_source_1_own_field_references",
            "control_guard_sha256": guard_sha256,
            "checkpoint_sha256": checkpoint_sha256,
            "threshold_policy": "fixed_from_control_no_recalibration",
            "threshold": control.threshold,
            "neighbors": control.neighbors,
            "control_reference_count": int(control.reference_embeddings.shape[0]),
            "external_reference_count": int(coffeeleaf_embeddings.shape[0]),
            "candidate_reference_count": int(candidate_references.shape[0]),
            "reference_count": int(candidate_references.shape[0]),
            "provenance_manifest_sha256": provenance_manifest_sha256,
            "coffeeleaf_reference_selection_sha256": coffeeleaf_verification[
                "selection_sha256"
            ],
            "coffeeleaf_reference_selection_md5": coffeeleaf_verification[
                "selection_md5"
            ],
            "rocole_test_images_opened": 0,
            "rocole_test_predictions_computed": 0,
            "rocole_test_used": False,
        }
        # El control histórico usa el nombre genérico `test_used`. Se elimina
        # para no confundir TEST de RoCoLe con una partición de otra fuente.
        candidate_metadata.pop("test_used", None)
        candidate = DomainGuard(
            reference_embeddings=candidate_references,
            threshold=control.threshold,
            neighbors=control.neighbors,
            metadata=candidate_metadata,
        )

        rocole_embeddings = embeddings_for_records(
            model,
            rocole_records,
            local_reader.read,
            args.batch_size,
        )
        ood_embeddings = embeddings_for_records(
            model,
            ood_records,
            ood_reader.read,
            args.batch_size,
        )
        control_rocole, candidate_rocole = scores_for_pair(
            control, candidate, rocole_embeddings
        )
        control_ood, candidate_ood = scores_for_pair(control, candidate, ood_embeddings)
        control_reference, candidate_reference = scores_for_pair(
            control, candidate, coffeeleaf_embeddings
        )

        metrics: dict[str, Any] = {
            "rocole_val_evaluation": comparison_metrics(
                rocole_records,
                control_rocole,
                candidate_rocole,
                control.threshold,
                positive=True,
            ),
            "known_ood_negatives": comparison_metrics(
                ood_records,
                control_ood,
                candidate_ood,
                control.threshold,
                positive=False,
            ),
            "coffeeleaf_reference_sanity_only": comparison_metrics(
                coffeeleaf_records,
                control_reference,
                candidate_reference,
                control.threshold,
                positive=True,
            ),
        }
        predictions: dict[str, list[dict[str, Any]]] = {
            "rocole_val_evaluation": prediction_rows(
                rocole_records,
                control_rocole,
                candidate_rocole,
                control.threshold,
            ),
            "known_ood_negatives": prediction_rows(
                ood_records,
                control_ood,
                candidate_ood,
                control.threshold,
            ),
            "coffeeleaf_reference_sanity_only": prediction_rows(
                coffeeleaf_records,
                control_reference,
                candidate_reference,
                control.threshold,
            ),
        }

        external_positive_metadata: dict[str, Any] = {"provided": False}
        if args.external_positive_manifest is not None:
            if not args.external_positive_manifest_sha256 or args.external_positive_root is None:
                raise ValueError(
                    "El manifiesto positivo reservado requiere tambien "
                    "--external-positive-manifest-sha256 y --external-positive-root"
                )
            external_manifest_path = args.external_positive_manifest.resolve()
            external_manifest_sha256 = verify_file_digest(
                external_manifest_path,
                args.external_positive_manifest_sha256,
                "sha256",
                "manifiesto positivo externo reservado",
            )
            external_root = args.external_positive_root.resolve()
            if not external_root.is_dir():
                raise ValueError(
                    f"--external-positive-root no es un directorio: {external_root}"
                )
            external_records = load_local_records(
                external_manifest_path,
                dataset="reserved_external_coffee_positive",
                root=external_root,
                expected_negative=False,
            )
            if any("rocole" in normalized_token(record.source) for record in external_records):
                raise ValueError(
                    "El manifiesto positivo reservado declara RoCoLe como fuente; no se permite"
                )
            ensure_no_overlap(
                external_records,
                test_hashes,
                "El positivo externo reservado (colision con TEST RoCoLe)",
            )
            ensure_no_overlap(
                external_records,
                {record.sha256 for record in coffeeleaf_records}
                | {record.sha256 for record in ood_records}
                | non_test_hashes,
                "El positivo externo reservado (contaminacion con desarrollo)",
            )
            with ByteStore(external_root) as external_reader:
                external_verification = verify_records(
                    external_records,
                    external_reader.read,
                    context="positivo externo reservado",
                )
                external_embeddings = embeddings_for_records(
                    model,
                    external_records,
                    external_reader.read,
                    args.batch_size,
                )
            control_external, candidate_external = scores_for_pair(
                control,
                candidate,
                external_embeddings,
            )
            metrics["reserved_external_coffee_positive"] = comparison_metrics(
                external_records,
                control_external,
                candidate_external,
                control.threshold,
                positive=True,
            )
            predictions["reserved_external_coffee_positive"] = prediction_rows(
                external_records,
                control_external,
                candidate_external,
                control.threshold,
            )
            external_positive_metadata = {
                "provided": True,
                "manifest_name": external_manifest_path.name,
                "manifest_sha256": external_manifest_sha256,
                "verification": external_verification,
                "opened_after_candidate_was_frozen": True,
            }
        elif args.external_positive_manifest_sha256 or args.external_positive_root:
            raise ValueError(
                "--external-positive-manifest-sha256/--external-positive-root no se "
                "pueden usar sin --external-positive-manifest"
            )
    finally:
        local_reader.close()
        ood_reader.close()

    output_dir.mkdir(parents=True, exist_ok=False)
    candidate_path = output_dir / "candidate_guard_not_integrated.pt"
    candidate.save(candidate_path)
    candidate_sha256 = sha256_file(candidate_path)
    for name, rows in predictions.items():
        write_csv(output_dir / f"{name}_scores.csv", rows)

    limitations = [
        "CoffeeLeaf-CO usado como referencia no es evaluacion independiente.",
        "El umbral y el numero de vecinos se conservaron; no se recalibraron.",
        "Las metricas por imagen no prueban independencia por planta o sesion.",
        "El score de similitud no es una probabilidad de que la imagen sea cafe.",
    ]
    if external_positive_metadata["provided"]:
        limitations.append(
            "La comprobacion positiva reservada comparte fuente y criterio de particion por imagen con las referencias; no equivale a evaluacion externa por planta."
        )
    else:
        limitations.append(
            "Sin un manifiesto positivo reservado no se mide cobertura fuera de RoCoLe."
        )

    summary = {
        "status": "complete_candidate_not_integrated",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "duration_seconds": time.perf_counter() - started,
        "rocole_test_used": False,
        "rocole_test_images_opened": 0,
        "rocole_test_predictions_computed": 0,
        "coffeeleaf_author_test_used_for_coverage_check": bool(
            external_positive_metadata["provided"]
        ),
        "intervention": "external_reference_addition_only",
        "model_training_performed": False,
        "threshold_selection_performed": False,
        "control": {
            "guard_name": guard_path.name,
            "guard_sha256": guard_sha256,
            "reference_count": int(control.reference_embeddings.shape[0]),
            "neighbors": control.neighbors,
            "threshold": control.threshold,
        },
        "candidate": {
            "artifact": candidate_path.name,
            "sha256": candidate_sha256,
            "reference_count": int(candidate.reference_embeddings.shape[0]),
            "neighbors_unchanged": candidate.neighbors,
            "threshold_unchanged": candidate.threshold,
            "integrated": False,
        },
        "checkpoint": {
            "name": checkpoint_path.name,
            "sha256": checkpoint_sha256,
            "model": checkpoint.get("model"),
            "classes": classes,
        },
        "preprocessing": {
            "source": "src.common.transform(training=False)",
            "exif_orientation": "ImageOps.exif_transpose",
            "color": "RGB",
            "resize": [224, 224],
            "resize_interpolation": "torchvision.transforms.Resize default (bilinear for PIL)",
            "tensor": "ToTensor",
            "normalization_mean": [0.485, 0.456, 0.406],
            "normalization_std": [0.229, 0.224, 0.225],
            "augmentation": False,
        },
        "inputs": {
            "coffeeleaf_source": source_container,
            "provenance_manifest_name": provenance_manifest_path.name,
            "provenance_manifest_sha256": provenance_manifest_sha256,
            "coffeeleaf_audit_selection": coffeeleaf_audit,
            "coffeeleaf_verification": coffeeleaf_verification,
            "rocole_manifest_name": rocole_manifest_path.name,
            "rocole_manifest_sha256": rocole_manifest_sha256,
            "rocole_val_evaluation_class_counts": rocole_counts,
            "rocole_val_verification": rocole_verification,
            "ood_manifest_name": ood_manifest_path.name,
            "ood_manifest_sha256": ood_manifest_sha256,
            "ood_verification": ood_verification,
            "external_positive": external_positive_metadata,
        },
        "metrics": metrics,
        "runtime": {
            "python": sys.version,
            "platform": platform.platform(),
            "torch": torch.__version__,
            "device": "cpu",
            "batch_size": args.batch_size,
        },
        "limitations": limitations,
    }
    (output_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    (output_dir / "configuration.json").write_text(
        json.dumps(candidate_metadata, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
