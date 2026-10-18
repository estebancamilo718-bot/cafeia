from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import torch
from torch import Tensor, nn
from torch.nn import functional as F


ARTIFACT_VERSION = 1


def mobilenet_logits_and_embedding(model: nn.Module, images: Tensor) -> tuple[Tensor, Tensor]:
    """Return logits and the normalized penultimate MobileNetV3 representation."""
    required = ("features", "avgpool", "classifier")
    if any(not hasattr(model, attribute) for attribute in required):
        raise TypeError("El filtro de dominio requiere un MobileNetV3 compatible")
    if len(model.classifier) != 4:
        raise ValueError("La estructura del clasificador MobileNetV3 no es la esperada")

    features = model.features(images)
    features = model.avgpool(features)
    features = torch.flatten(features, 1)
    features = model.classifier[0](features)
    features = model.classifier[1](features)
    embedding = F.normalize(features, p=2, dim=1)
    logits = model.classifier[3](model.classifier[2](features))
    return logits, embedding


def extract_mobilenet_embedding(model: nn.Module, images: Tensor) -> Tensor:
    return mobilenet_logits_and_embedding(model, images)[1]


def domain_similarity(
    embeddings: Tensor,
    reference_embeddings: Tensor,
    *,
    neighbors: int,
) -> Tensor:
    if embeddings.ndim != 2 or reference_embeddings.ndim != 2:
        raise ValueError("Los embeddings deben tener forma [N, D]")
    if embeddings.shape[1] != reference_embeddings.shape[1]:
        raise ValueError("La dimensión de los embeddings no coincide")
    if not 1 <= neighbors <= reference_embeddings.shape[0]:
        raise ValueError("Cantidad de vecinos inválida")

    similarities = embeddings @ reference_embeddings.T
    return similarities.topk(neighbors, dim=1).values.mean(dim=1)


@dataclass(frozen=True)
class DomainGuard:
    reference_embeddings: Tensor
    threshold: float
    neighbors: int
    metadata: dict[str, Any]

    def scores(self, embeddings: Tensor) -> Tensor:
        return domain_similarity(
            embeddings,
            self.reference_embeddings,
            neighbors=self.neighbors,
        )

    def accepts(self, embeddings: Tensor) -> Tensor:
        return self.scores(embeddings) >= self.threshold

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        torch.save(
            {
                "artifact_version": ARTIFACT_VERSION,
                "reference_embeddings": self.reference_embeddings.cpu(),
                "threshold": self.threshold,
                "neighbors": self.neighbors,
                "metadata": self.metadata,
            },
            path,
        )

    @classmethod
    def load(cls, path: Path) -> "DomainGuard":
        payload = torch.load(path, map_location="cpu", weights_only=True)
        if payload.get("artifact_version") != ARTIFACT_VERSION:
            raise ValueError("Versión de filtro de dominio incompatible")
        references = payload.get("reference_embeddings")
        if not isinstance(references, Tensor) or references.ndim != 2:
            raise ValueError("Banco de referencias inválido")
        if not torch.isfinite(references).all():
            raise ValueError("El banco de referencias contiene valores no finitos")
        threshold = float(payload["threshold"])
        neighbors = int(payload["neighbors"])
        if not -1.0 <= threshold <= 1.0:
            raise ValueError("Umbral de similitud inválido")
        if not 1 <= neighbors <= references.shape[0]:
            raise ValueError("Cantidad de vecinos inválida")
        return cls(
            reference_embeddings=references,
            threshold=threshold,
            neighbors=neighbors,
            metadata=dict(payload.get("metadata", {})),
        )
