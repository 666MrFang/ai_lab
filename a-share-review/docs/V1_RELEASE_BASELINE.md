# A-Share Review V1.0 Release Baseline

Status: **RELEASE CANDIDATE**

## Deterministic acceptance

The master CI is the executable acceptance gate. V1.0 requires:

- Product deterministic suite: PASS
- Market MCP deterministic suite: PASS
- Temporal integrity: fail closed
- Schema / contract / evidence integrity: fail closed
- Independent Eval: PASS for publication
- Golden hard violations: BLOCK publication
- Missing evidence: explicit, never coerced to zero or PASS
- D+1 verification: OBSERVED_PASS / OBSERVED_FAIL / NOT_OBSERVABLE

Baseline established on 2026-10-06:

- Product: 119 passed
- Market MCP: 114 passed
- Total: 233 passed
- GitHub Actions run: 37489483330
- Master commit: 10a4a7f7b34486687e0cbade6d1daeb7557a030c

## Real-agent acceptance

DeepSeek Flash has already completed a full controlled A/B replay on the frozen
2026-09-30 Evidence Store through schema, contract, integrity and independent
evaluation. This proves the real-agent adapter path, not superiority over the
ReferenceAgent.

A release remains **RC** until the current master is executed end-to-end through
`review_product.py --agent deepseek` in an environment containing a valid
`DEEPSEEK_API_KEY`, and returns `PUBLICATION_STATUS=PUBLISHED`.

## Golden corpus policy

Golden cases are created only for dates with frozen Evidence Store artifacts.
The repository currently contains frozen evidence for 2026-09-30, therefore
V1.0 does not fabricate additional historical cases merely to reach a target
case count. The corpus grows with real daily operation.

Golden constraints test behavior, not exact prose or hindsight returns. They
must never encode facts unsupported by the corresponding frozen evidence.

## Daily entry

Windows:

```powershell
$env:DEEPSEEK_API_KEY = "<set locally; never commit>"
.\scripts\run_daily.ps1 -Date YYYY-MM-DD
```

Direct:

```powershell
python review_product.py --date YYYY-MM-DD --mode auto --agent deepseek --model deepseek-flash
```

A generated dashboard is not sufficient for publication. Only
`PUBLICATION_STATUS=PUBLISHED` is a successful daily product result.
