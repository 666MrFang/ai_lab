"""Replay: load previously saved evidence. Never touches the network."""

from __future__ import annotations

from typing import Any, Dict

from .store import EvidenceStore


def replay_market(store: EvidenceStore, date: str) -> Dict[str, Any]:
    """Return stored evidence for ``date`` or raise ``ReplayDataNotFound``.

    There is deliberately NO fallback to LIVE collection: a missing replay is
    an explicit error, never a silent re-fetch from the upstream API.
    """

    return store.load(date)
