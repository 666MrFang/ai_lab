"""Semantic calibration policy for the independent Eval Harness.

This round deliberately does NOT hardcode "0-20 = very low, 20-40 = low, ..."
as fact. Thresholds belong to an explicit Eval Policy fixture supplied by each
case, so the provider/domain layer stays free of semantic opinions. Once the
Skill's calibration is agreed, a formal policy can be frozen here.

Policy fixture shape (per case)::

    {
      "high": {"percentile_gte": 80},
      "low":  {"percentile_lte": 20}
    }
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from models import HIGH_LABELS, LOW_LABELS


@dataclass(frozen=True)
class SemanticCalibrationPolicy:
    high_percentile_gte: Optional[float] = None
    low_percentile_lte: Optional[float] = None

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> "SemanticCalibrationPolicy":
        if not data:
            return cls()
        return cls(
            high_percentile_gte=(data.get("high") or {}).get("percentile_gte"),
            low_percentile_lte=(data.get("low") or {}).get("percentile_lte"),
        )

    def label_supported(self, label: str, percentile: Optional[float]) -> Optional[bool]:
        """Return whether ``label`` is supported by the percentile.

        ``None`` means the policy cannot judge (missing threshold or percentile).
        """

        if label in HIGH_LABELS:
            if self.high_percentile_gte is None or percentile is None:
                return None
            return percentile >= self.high_percentile_gte
        if label in LOW_LABELS:
            if self.low_percentile_lte is None or percentile is None:
                return None
            return percentile <= self.low_percentile_lte
        return None
