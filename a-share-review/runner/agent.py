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
                "turnover_cny": row.get("turnover_cny"),
                "change_5d_pct": None,
                "change_20d_pct": None,
            }

        top_gainers = [sector_view(row) for row in sector_rows[:5]]
        top_losers = [sector_view(row) for row in list(reversed(sector_rows[-5:]))]
        main_theme_candidates = [
            {
                "sector_name": row.get("sector_name") or "UNKNOWN",
                "confidence": "LOW",
                "evidence": [_ev(
                    "THS industry rank=%d change_pct=%s turnover_cny=%s"
                    % (rank + 1, row.get("change_pct"), row.get("turnover_cny")),
                    "evidence_store",
                    "MEDIUM",
                )],
                "evidence_gaps": [
                    "缺少同口径历史横截面排名/板块内部核心股与事件证据"
                ],
            }
            for rank, row in enumerate(sector_rows[:3])
        ]

        # --- stocks -------------------------------------------------------
        stocks: List[Dict[str, Any]] = []
        seen_stock_codes = set()

        # Membership is a separate Sina evidence family. It may identify
        # capacity-core *candidates* (market cap >= 50B CNY), but it must not
        # be presented as THS internal contribution or as a confirmed leader.
        memberships = normalized.get("sector_memberships") or {}
        stock_history = normalized.get("stock_history") or {}
        strong_codes_by_sector: Dict[str, set] = {}
        strong_rank_by_code: Dict[str, int] = {}

        # "STRONG_STOCK" is deliberately strict: only when every stock in the
        # current Sina membership has a complete comparable 5d history can we
        # assert a true sector Top3. Partial coverage cannot manufacture Top3.
        for membership in memberships.values():
            sector_name = membership.get("sector_name") or "UNKNOWN"
            members = list(membership.get("stocks") or [])
            ranked = []
            complete = bool(members)
            for member in members:
                code = member.get("stock_code")
                hist = stock_history.get(str(code)) or {}
                if not code or hist.get("history_5d_complete") is not True or hist.get("change_pct_5d") is None:
                    complete = False
                    break
                ranked.append((float(hist["change_pct_5d"]), str(code)))
            if complete:
                ranked.sort(key=lambda item: (-item[0], item[1]))
                top = ranked[:3]
                strong_codes_by_sector[sector_name] = {code for _, code in top}
                for rank, (_, code) in enumerate(top, start=1):
                    strong_rank_by_code[code] = rank

        for membership in memberships.values():
            sector_name = membership.get("sector_name") or "UNKNOWN"
            members = list(membership.get("stocks") or [])
            members.sort(
                key=lambda item: item.get("change_pct")
                if item.get("change_pct") is not None else float("-inf"),
                reverse=True,
            )
            for current_rank, member in enumerate(members, start=1):
                code = member.get("stock_code")
                market_cap = member.get("market_cap_cny")
                if not code or code in seen_stock_codes:
                    continue
                is_capacity = market_cap is not None and float(market_cap) >= 50_000_000_000
                is_strong = code in strong_codes_by_sector.get(sector_name, set())
                # Keep all capacity candidates, true 5d strong stocks, plus
                # today's top-3 movers for observation.
                if not is_capacity and not is_strong and current_rank > 3:
                    continue
                roles = []
                if is_strong:
                    roles.append("STRONG_STOCK")
                if is_capacity:
                    roles.append("CAPACITY_CORE_CANDIDATE")
                if not roles:
                    roles = ["OTHER"]
                hist = stock_history.get(str(code)) or {}
                gaps = [
                    "Sina CURRENT_MEMBERSHIP_ONLY；不得当作 THS 板块内部贡献证据",
                    "STRONG_STOCK仅表示当前Sina成员中完整5日涨幅Top3，不等同于龙头",
                    "缺少新闻/公告证据，不能判断上涨原因",
                ]
                if not is_strong:
                    gaps.append("板块成员5d历史覆盖不完整或未进入Top3，不能标记STRONG_STOCK")
                stocks.append({
                    "code": code,
                    "name": member.get("stock_name") or "UNKNOWN",
                    "sector_name": sector_name,
                    "roles": roles,
                    "facts": [{
                        "statement": (
                            "Sina当前成员：涨跌幅 %s%%，成交额 %s 元，换手率 %s%%，市值 %s 元。"
                            % (member.get("change_pct"), member.get("turnover_cny"),
                               member.get("turnover_rate_pct"), market_cap)
                        ),
                        "source": "evidence_store:sina_membership",
                    }, {
                        "statement": (
                            "5日涨幅 %s%%，5日完整=%s，板块5日排名=%s。"
                            % (hist.get("change_pct_5d"), hist.get("history_5d_complete"),
                               strong_rank_by_code.get(code))
                        ),
                        "source": "evidence_store:sina_stock_history",
                    }],
                    "possible_drivers": [],
                    "historical_behavior": None,
                    "evidence_gaps": gaps,
                })
                seen_stock_codes.add(code)

        for key in sorted(store):
            if not key.startswith("stock_detail:"):
                continue
            stock = store[key]
            code = stock.get("code")
            if code in seen_stock_codes:
                continue
            stocks.append({
                "code": code, "name": stock.get("name") or "UNKNOWN",
                "sector_name": "UNKNOWN", "roles": ["OTHER"],
                "facts": [{"statement": "收盘 %s，涨跌幅 %s%%."
                           % (stock.get("close"), stock.get("change_pct")),
                           "source": "evidence_store"}],
                "possible_drivers": [], "historical_behavior": None,
                "evidence_gaps": ["no verified sector membership / news evidence"],
            })

        # News is timestamped event evidence only. Existence of an item is
        # never promoted to a price-move cause without minute-level ordering
        # and an explicit causal policy.
        news_map = normalized.get("stock_news") or {}
        for stock in stocks:
            news = news_map.get(str(stock.get("code"))) or {}
            items = list(news.get("news") or [])
            for item in items[:3]:
                stock["facts"].append({
                    "statement": "新闻 %s [%s] %s"
                                 % (item.get("published_at"), item.get("source"),
                                    item.get("title")),
                    "source": item.get("url") or "eastmoney:stock_news_em",
                })
            if items:
                stock["evidence_gaps"] = [
                    gap for gap in stock.get("evidence_gaps") or []
                    if "新闻/公告" not in gap and "news" not in gap
                ]
                stock["evidence_gaps"].append(
                    "新闻存在不等于涨跌原因；缺少分钟级价格顺序/因果证据"
                )

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
                "target": "market turnover persistence",
                "condition": "next-session market_turnover > 0",
                "meaning": "验证下一交易日成交额证据是否可观测；不构成方向预测",
                "condition_id": "W001",
                "metric": "market_turnover",
                "operator": "gt",
                "expected_value": 0,
                "horizon_sessions": 1,
                "evidence_ref": None,
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
