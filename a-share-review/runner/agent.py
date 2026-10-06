"""Reference Agent (deterministic) for the Production Runner.

V0.1 stand-in for an LLM agent: it consumes ONLY stored Evidence (never the
Market MCP) and emits a schema-compliant review that follows the frozen Skill
rules (persistence gate -> UNCERTAIN; FACT/RELATIVE_NUMERIC over SEMANTIC).

The runner's Agent stage is pluggable; this reference agent keeps the pipeline
executable and reproducible without an LLM dependency.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List

from .identity import SKILL_PATH, SCHEMA_PATH

CLAIM_METRICS = (
    ("broken_limit_rate", "percent"),
    ("promotion_rate", "percent"),
    ("limit_up_count", "count"),
    ("market_turnover", "cny"),
)


def _ev(statement: str, source: str, strength: str = "HIGH") -> Dict[str, str]:
    return {"statement": statement, "source": source, "strength": strength}


class ReferenceAgent:
    name = "reference-agent-v0.1"

    def __call__(self, agent_input: Dict[str, Any]) -> Dict[str, Any]:
        review = self.build_review(agent_input)
        markdown = self.render_markdown(review, agent_input)
        return {
            "review": review,
            "review_md": markdown,
            "raw": json.dumps(review, ensure_ascii=False),
        }

    # ------------------------------------------------------------------
    def build_review(self, agent_input: Dict[str, Any]) -> Dict[str, Any]:
        date = agent_input["date"]
        manifest = agent_input.get("manifest") or {}
        normalized = agent_input.get("normalized") or {}
        store = normalized.get("evidence", {})

        metric_keys = sorted(
            key for key, value in store.items()
            if value.get("evidence_type") in ("market_metric", "market_metric_baseline")
        )
        eid = {key: "E%03d" % (index + 1) for index, key in enumerate(metric_keys)}

        registry: List[Dict[str, Any]] = []
        for key in metric_keys:
            value = store[key]
            if value["evidence_type"] == "market_metric":
                registry.append({
                    "evidence_id": eid[key], "evidence_type": "market_metric",
                    "metric": value.get("metric"), "date": value.get("date"),
                    "window": None, "value": value.get("value"),
                    "avg": None, "median": None, "percentile": None,
                    "sample_count": None, "complete": None, "unit": value.get("unit"),
                    "source": value.get("source"),
                })
            else:
                registry.append({
                    "evidence_id": eid[key], "evidence_type": "market_metric_baseline",
                    "metric": value.get("metric"), "date": value.get("date"),
                    "window": value.get("window"), "value": value.get("current"),
                    "avg": value.get("avg"), "median": value.get("median"),
                    "percentile": value.get("percentile"),
                    "sample_count": value.get("sample_count"),
                    "complete": value.get("complete"), "unit": value.get("unit"),
                    "source": value.get("source"),
                })

        def metric_entry(metric: str) -> Dict[str, Any] | None:
            return store.get("market_metric:%s:%s" % (metric, date))

        def baseline_entry(metric: str, window: int) -> Dict[str, Any] | None:
            return store.get("market_metric_baseline:%s:%s:%s" % (metric, date, window))

        # --- metric_claims (FACT / RELATIVE_NUMERIC only) -----------------
        claims: List[Dict[str, Any]] = []
        counter = 0

        def add_claim(ctype, metric, value, unit, baseline_refs, evidence_refs):
            nonlocal counter
            counter += 1
            claims.append({
                "claim_id": "C%03d" % counter, "metric": metric, "claim_type": ctype,
                "current_value": value, "unit": unit, "semantic_label": None,
                "baseline_refs": baseline_refs, "threshold_policy_ref": None,
                "evidence_refs": evidence_refs, "forward_claim": False, "text_ref": None,
            })

        for metric, default_unit in CLAIM_METRICS:
            current = metric_entry(metric)
            if current is None or current.get("value") is None:
                continue
            mk = "market_metric:%s:%s" % (metric, date)
            add_claim("FACT", metric, current.get("value"),
                      current.get("unit") or default_unit, [], [eid[mk]])
            for window in (5, 20):
                baseline = baseline_entry(metric, window)
                if baseline is not None and baseline.get("complete") is True:
                    bk = "market_metric_baseline:%s:%s:%s" % (metric, date, window)
                    add_claim("RELATIVE_NUMERIC", metric, current.get("value"),
                              current.get("unit") or default_unit, [eid[bk]],
                              [eid[mk], eid[bk]])
                    break

        # --- facts / inferences ------------------------------------------
        facts: List[Dict[str, str]] = []
        inferences: List[Dict[str, Any]] = []
        for key in sorted(store):
            if key.startswith("index_quote:"):
                quote = store[key]
                facts.append({
                    "statement": "%s 收盘 %s，涨跌幅 %s%%。"
                                 % (quote.get("index"), quote.get("close"), quote.get("change_pct")),
                    "source": "evidence_store",
                })
        turnover = metric_entry("market_turnover")
        if turnover and turnover.get("value") is not None:
            facts.append({"statement": "两市成交额 %s 元。" % turnover.get("value"),
                          "source": "evidence_store"})
        for metric in ("limit_up_count", "limit_down_count", "broken_limit_rate", "promotion_rate"):
            entry = metric_entry(metric)
            if entry and entry.get("value") is not None:
                facts.append({"statement": "%s = %s。" % (metric, entry.get("value")),
                              "source": "evidence_store"})

        for metric in ("broken_limit_rate", "promotion_rate"):
            current = metric_entry(metric)
            baseline = baseline_entry(metric, 5)
            if current and baseline and baseline.get("complete") is True:
                mk = "market_metric:%s:%s" % (metric, date)
                bk = "market_metric_baseline:%s:%s:5" % (metric, date)
                relation = "低于" if (current.get("value") or 0) < (baseline.get("avg") or 0) else "不低于"
                inferences.append({
                    "claim": "%s 当前 %s，%s近 5 日均值 %s（历史分位 %s）。"
                             % (metric, current.get("value"), relation,
                                baseline.get("avg"), baseline.get("percentile")),
                    "confidence": "MEDIUM",
                    "evidence": [_ev("stored %s and 5d baseline" % metric, "evidence_store")],
                    "counter_evidence": [],
                    "evidence_gaps": [],
                })

        # --- regime (persistence gate) -----------------------------------
        incomplete = list(manifest.get("incomplete_evidence") or [])
        missing_caps = list(manifest.get("missing_capabilities") or [])
        regime_evidence = [_ev("current-day evidence from stored Tool responses",
                               "evidence_store", "MEDIUM")]
        regime_gaps = ["insufficient persistence evidence: %s" % key for key in incomplete]
        regime_gaps += ["missing capability: %s" % name for name in missing_caps]
        market_regime = {
            "state": "UNCERTAIN", "confidence": "LOW",
            "evidence": regime_evidence if not incomplete else [],
            "counter_evidence": [
                _ev("incomplete persistence baseline: %s" % key, "evidence_store")
                for key in incomplete
            ],
            "evidence_gaps": regime_gaps or ["insufficient persistence evidence"],
        }

        # --- sectors ------------------------------------------------------
        sector_rows = list((normalized.get("sector_ranking") or {}).get("sectors") or [])
        sector_rows = sorted(
            sector_rows,
            key=lambda row: row.get("change_pct")
            if row.get("change_pct") is not None else float("-inf"),
            reverse=True,
        )

        def sector_view(row: Dict[str, Any]) -> Dict[str, Any]:
            return {
                "sector_name": row.get("sector_name") or "UNKNOWN",
                "change_pct": row.get("change_pct"),
                "turnover": row.get("turnover_cny"),
                "leading_stocks": [],
                "evidence": [_ev(
                    "THS industry snapshot; up=%s down=%s"
                    % (row.get("up_count"), row.get("down_count")),
                    "evidence_store",
                )],
            }

        top_gainers = [sector_view(row) for row in sector_rows[:5]]
        top_losers = [sector_view(row) for row in list(reversed(sector_rows[-5:]))]
        main_theme_candidates = [
            {
                "sector_name": row.get("sector_name") or "UNKNOWN",
                "status": "CANDIDATE",
                "reason": "当日行业涨幅排名 Top%d；仅为候选，不等同于主线确认。" % (rank + 1),
                "evidence": [_ev(
                    "THS industry rank=%d change_pct=%s turnover_cny=%s"
                    % (rank + 1, row.get("change_pct"), row.get("turnover_cny")),
                    "evidence_store",
                    "MEDIUM",
                )],
                "counter_evidence": [],
                "evidence_gaps": [
                    "缺少同口径历史横截面排名/板块内部核心股与事件证据"
                ],
            }
            for rank, row in enumerate(sector_rows[:3])
        ]

        # --- stocks -------------------------------------------------------
        stocks: List[Dict[str, Any]] = []
        for key in sorted(store):
            if not key.startswith("stock_detail:"):
                continue
            stock = store[key]
            stocks.append({
                "code": stock.get("code"), "name": stock.get("name") or "UNKNOWN",
                "sector_name": "UNKNOWN", "roles": ["OTHER"],
                "facts": [{"statement": "收盘 %s，涨跌幅 %s%%."
                           % (stock.get("close"), stock.get("change_pct")),
                           "source": "evidence_store"}],
                "possible_drivers": [], "historical_behavior": None,
                "evidence_gaps": ["no sector / news capability"],
            })

        broken = metric_entry("broken_limit_rate")
        promotion = metric_entry("promotion_rate")
        profit_effect = {
            "summary": "promotion_rate = %s。" % (promotion.get("value") if promotion else None),
            "confidence": "LOW",
            "evidence": [_ev("stored breadth metrics", "evidence_store")],
            "evidence_gaps": [],
        }
        loss_effect = {
            "summary": "broken_limit_rate = %s。" % (broken.get("value") if broken else None),
            "confidence": "LOW",
            "evidence": [_ev("stored breadth metrics", "evidence_store")],
            "evidence_gaps": [],
        }

        review = {
            "date": date,
            "market": {"facts": facts, "inferences": inferences},
            "market_regime": market_regime,
            "sectors": {
                "top_gainers": top_gainers,
                "top_losers": top_losers,
                "main_theme_candidates": main_theme_candidates,
            },
            "stocks": stocks,
            "profit_effect": profit_effect,
            "loss_effect": loss_effect,
            "evidence_gaps": regime_gaps,
            "tomorrow_watch_conditions": [{
                "target": "persistence baseline",
                "condition": "20d metric baseline complete=true",
                "meaning": "persistence 证据是否充分，决定能否确认 regime",
            }],
            "metric_claims": claims,
            "evidence_registry": registry,
        }
        return review

    # ------------------------------------------------------------------
    @staticmethod
    def render_markdown(review: Dict[str, Any], agent_input: Dict[str, Any]) -> str:
        lines = ["# A股盘后复盘 — %s" % review.get("date"), "",
                 "> Reference Agent V0.1（deterministic，仅消费 Evidence Store）。", ""]
        lines.append("## 市场 Fact")
        for fact in review.get("market", {}).get("facts", []):
            lines.append("- %s" % fact.get("statement"))
        lines.append("")
        lines.append("## Market Regime")
        regime = review.get("market_regime", {})
        lines.append("- state = %s, confidence = %s" % (regime.get("state"), regime.get("confidence")))
        for gap in regime.get("evidence_gaps", []):
            lines.append("- evidence_gap: %s" % gap)
        lines.append("")
        lines.append("## 行业板块")
        for sector in (review.get("sectors") or {}).get("top_gainers") or []:
            lines.append("- 强势候选：%s %s%%，成交额 %s 元"
                         % (sector.get("sector_name"), sector.get("change_pct"),
                            sector.get("turnover")))
        for sector in (review.get("sectors") or {}).get("top_losers") or []:
            lines.append("- 弱势：%s %s%%"
                         % (sector.get("sector_name"), sector.get("change_pct")))
        lines.append("")
        lines.append("## MetricClaims")
        for claim in review.get("metric_claims", []):
            lines.append("- %s %s = %s (%s)"
                         % (claim.get("claim_id"), claim.get("metric"),
                            claim.get("current_value"), claim.get("claim_type")))
        return "\n".join(lines) + "\n"
