# Review Memory V0.1

The daily review is now treated as a learning record rather than disposable prose.

## Data lifecycle

1. Daily review produces structured review + Evidence Store.
2. `review_memory_cli.py ingest --date YYYY-MM-DD` freezes the decision-time snapshot.
3. When later trading-session Evidence Store snapshots exist, `settle` attaches T+1/T+3/T+5 realised sector outcomes.
4. `outlook` matches only **SETTLED records strictly earlier than the review date**.
5. Statistics are exposed only when sample size reaches the configured minimum (default 8).

The output deliberately says `HISTORICAL_CALIBRATION_NOT_PREDICTION`. A historical positive rate is evidence about the sample, not a promise about tomorrow.

## Pattern V0.1

The first deterministic signature uses:

- Shanghai Composite direction: UP > +0.5%, DOWN < -0.5%, otherwise FLAT.
- Sector daily move: >=4% surge, >=2% strong, <=-2% weak, otherwise normal.
- Sector rank: TOP1 / TOP3 / TOP5 / OTHER.

This is intentionally simple and versioned. Future rounds can add turnover percentile, market regime, breadth, sector persistence, leader state and event type without rewriting old records.

## Commands

```
python review_memory_cli.py ingest --date 2026-10-XX
python review_memory_cli.py settle --date 2026-10-XX
python review_memory_cli.py outlook --date 2026-10-XX
```

A useful outlook requires accumulated, settled daily snapshots. Missing history remains an Evidence Gap; it is never filled by model intuition.
