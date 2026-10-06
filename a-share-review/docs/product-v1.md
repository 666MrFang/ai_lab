# A-Share Review Product V1

## One command

```powershell
python review_product.py --date YYYY-MM-DD --mode live
```

After the first collection, the same date can be reproduced without Market MCP:

```powershell
python review_product.py --date YYYY-MM-DD --mode replay --overwrite-output
```

Artifacts:

- `output/<date>/review.md` — human-readable daily review
- `output/<date>/review.json` — structured claims and evidence
- `output/<date>/eval.json` — independent F001/F002 evaluation
- `output/<date>/outlook.json` — historical T+1/T+3/T+5 calibration
- `output/<date>/dashboard.html` — zero-dependency dashboard
- `output/<date>/run_manifest.json` — reproducibility identity
- `data/review_history/<date>/record.json` — decision-time review memory

## What V1 can do

V1 captures market/index/breadth facts and the complete THS industry ranking, emits
Top/Bottom sector facts, persists the review, and automatically settles older review
records when later Evidence Store snapshots exist. Historical outlooks are
sector-specific and use only SETTLED records strictly earlier than the review date.

The first pattern signature is deliberately conservative: market direction + sector
daily-move bucket + sector-rank bucket. It reports T+1/T+3/T+5 sample statistics only
after the minimum sample size (default 8) is reached.

## Safety / evidence boundary

- Historical Pattern != Future Fact.
- Same numeric pattern in a different sector is not borrowed as evidence for this sector.
- Future-dated records are excluded.
- Missing history remains `INSUFFICIENT_SAMPLE`.
- Sector Top1 is a strong-sector candidate, not automatically the market main line.
- Current THS ranking and Sina membership are separate evidence families.
- News causality remains unsupported until timestamp-aligned event/minute evidence exists.
- V1 does not make buy/sell recommendations.

## Current product gaps

The deterministic ReferenceAgent remains the default generator. It is useful for
reproducibility but is not yet a language-model research agent. Stock/core-leader
coverage is limited because verified THS -> Sina membership mappings are intentionally
sparse. Real news remains unimplemented. Historical cross-sectional sector snapshots
start accumulating from deployment; upstream cannot reconstruct all old dates.

Those gaps are surfaced rather than filled by model intuition.
