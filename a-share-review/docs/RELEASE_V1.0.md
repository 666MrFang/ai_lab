# A-Share Review V1.0

Released: 2026-10-06

V1.0 is the first daily-usable release of the evidence-constrained A-share
review system.

## Acceptance evidence

Deterministic CI baseline:

- Product: 119 / 119 PASS
- Market MCP: 114 / 114 PASS
- Total: 233 / 233 PASS
- GitHub Actions run: 37489483330

Real DeepSeek acceptance on frozen 2026-09-30 evidence:

- Agent: PASS
- Schema: PASS
- Contract: PASS
- Evidence integrity: PASS
- Independent Eval: PASS (F001 / F002)
- Golden: PASS
- Publication: PUBLISHED

## V1.0 guarantees

V1.0 is designed to fail closed. It does not promise correct market
predictions. It guarantees that a published review has passed the implemented
evidence, structure, contract, integrity, evaluation and Golden gates.

Current-only evidence cannot silently become historical evidence. Missing
evidence is explicit. News existence is not causal proof. Historical
calibration is not a prediction promise. NOT_OBSERVABLE is not PASS.

## Post-V1 growth

The Golden corpus and Review Memory are intentionally accumulated from real
daily frozen evidence. They must not be backfilled with fabricated historical
facts merely to increase sample counts.
