from __future__ import annotations

import torch
from torch import nn

from src.domain_guard import DomainGuard, domain_similarity, mobilenet_logits_and_embedding


def test_domain_similarity_uses_mean_of_nearest_cosine_neighbors() -> None:
    references = torch.tensor([[1.0, 0.0], [0.8, 0.6], [0.0, 1.0]])
    embeddings = torch.tensor([[1.0, 0.0]])

    score = domain_similarity(embeddings, references, neighbors=2)

    assert torch.allclose(score, torch.tensor([0.9]))


def test_guard_accepts_only_scores_at_or_above_threshold() -> None:
    guard = DomainGuard(
        reference_embeddings=torch.tensor([[1.0, 0.0]]),
        threshold=0.8,
        neighbors=1,
        metadata={},
    )
    embeddings = torch.tensor([[1.0, 0.0], [0.5, 0.5]])

    assert guard.accepts(embeddings).tolist() == [True, False]


def test_guard_round_trip(tmp_path) -> None:
    path = tmp_path / "guard.pt"
    original = DomainGuard(
        reference_embeddings=torch.tensor([[1.0, 0.0], [0.0, 1.0]]),
        threshold=0.75,
        neighbors=1,
        metadata={"checkpoint_sha256": "abc"},
    )

    original.save(path)
    loaded = DomainGuard.load(path)

    assert loaded.threshold == original.threshold
    assert loaded.neighbors == original.neighbors
    assert loaded.metadata == original.metadata
    assert torch.equal(loaded.reference_embeddings, original.reference_embeddings)


class TinyMobileNet(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.features = nn.Identity()
        self.avgpool = nn.AdaptiveAvgPool2d(1)
        self.classifier = nn.Sequential(
            nn.Linear(3, 4),
            nn.Hardswish(),
            nn.Dropout(0.2),
            nn.Linear(4, 3),
        )

    def forward(self, images: torch.Tensor) -> torch.Tensor:
        features = self.avgpool(self.features(images))
        return self.classifier(torch.flatten(features, 1))


def test_combined_forward_preserves_model_logits() -> None:
    model = TinyMobileNet().eval()
    images = torch.rand(2, 3, 8, 8)

    logits, embeddings = mobilenet_logits_and_embedding(model, images)

    assert torch.allclose(logits, model(images))
    assert torch.allclose(torch.linalg.vector_norm(embeddings, dim=1), torch.ones(2))
