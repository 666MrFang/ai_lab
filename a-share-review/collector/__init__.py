"""Production market evidence collection (Round 4A).

Collection != Analysis:
    collector collects Tool Evidence and persists it under
    ``data/market/<date>/`` (raw + normalized + manifest).
It never runs the Agent, the Eval harness, or generates review.md.
"""

from .collector import Collection, RawRecord, collect, normalized_for
from .replay import replay_market
from .store import (
    CollectionNotPublishable,
    EvidenceStore,
    OverwriteRefused,
    ReplayDataNotFound,
)

__all__ = [
    "Collection",
    "RawRecord",
    "collect",
    "normalized_for",
    "replay_market",
    "EvidenceStore",
    "OverwriteRefused",
    "CollectionNotPublishable",
    "ReplayDataNotFound",
]
