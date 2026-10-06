"""Deterministic normalization of raw market tool responses.

Produces ``normalized/market.json`` keyed by *deterministic* evidence keys
(never random E001/E002), so the same evidence always maps to the same key.
"""

from __future__ import annotations

from typing import Any, Dict, List

from .capabilities import baseline_key, index_key, metric_key, stock_key


def extract_lineage(result: Any) -> List[Dict[str, str]]:
    """Collect source/endpoint lineage exposed by a tool result (if any)."""

    lineage: List[Dict[str, str]] = []
    seen = set()

    def add(source: Any, endpoint: Any) -> None:
        if source and endpoint:
            key = (str(source), str(endpoint))
            if key not in seen:
                seen.add(key)
                lineage.append({"source": str(source), "endpoint": str(endpoint)})

    if not isinstance(result, dict):
        return lineage

    definitions = (result.get("evidence") or {}).get("definitions")
    if isinstance(definitions, dict):
        for definition in definitions.values():
            if isinstance(definition, dict):
                add(definition.get("source"), definition.get("endpoint"))

    definition = (result.get("baseline") or {}).get("definition")
    if isinstance(definition, dict):
        add(definition.get("source"), definition.get("endpoint"))

    return lineage


_LIMIT_METRICS = (
    ("limit_up_count", "count"),
    ("limit_down_count", "count"),
    ("broken_limit_count", "count"),
    ("broken_limit_rate", "percent"),
    ("first_limit_up_count", "count"),
    ("multi_limit_up_count", "count"),
    ("max_limit_height", "count"),
)


def normalize_records(records: List[Any], date: str) -> Dict[str, Any]:
    evidence: Dict[str, Any] = {}
    sector_ranking: Dict[str, Any] = {
        "date": date,
        "taxonomy": "industry",
        "source_family": "ths",
        "date_semantics": "CURRENT_ONLY",
        "sectors": [],
    }

    for record in records:
        if not record.success or not isinstance(record.result, dict):
            continue
        result = record.result

        if record.tool == "get_sector_ranking":
            for sector in result.get("sectors") or []:
                sector_ranking["sectors"].append(
                    {
                        "sector_id": sector.get("sector_id"),
                        "sector_name": sector.get("sector_name"),
                        "taxonomy": sector.get("taxonomy", "industry"),
                        "change_pct": sector.get("change_pct"),
                        "turnover_cny": sector.get("turnover_cny", sector.get("turnover")),
                        "up_count": sector.get("up_count"),
                        "down_count": sector.get("down_count"),
                        "flat_count": sector.get("flat_count"),
                        "constituent_count": sector.get("constituent_count"),
                    }
                )

        if record.tool == "get_market_breadth":
            limit = result.get("limit_state") or {}
            previous = result.get("previous_limit_up") or {}
            for metric, unit in _LIMIT_METRICS:
                evidence[metric_key(metric, date)] = {
                    "evidence_type": "market_metric",
                    "metric": metric,
                    "date": date,
                    "value": limit.get(metric),
                    "unit": unit,
                    "source": "eastmoney",
                }
            evidence[metric_key("promotion_rate", date)] = {
                "evidence_type": "market_metric",
                "metric": "promotion_rate",
                "date": date,
                "value": previous.get("promotion_rate"),
                "unit": "percent",
                "source": "eastmoney",
            }

        elif record.tool == "get_market_history_summary":
            turnover = result.get("turnover") or {}
            evidence[metric_key("market_turnover", date)] = {
                "evidence_type": "market_metric",
                "metric": "market_turnover",
                "date": date,
                "value": turnover.get("current_cny"),
                "unit": "cny",
                "source": "sse+szse",
            }

        elif record.tool == "get_market_metric_baseline":
            baseline = result.get("baseline") or {}
            metric = baseline.get("metric")
            window = baseline.get("window")
            if metric is None or window is None:
                continue
            definition = baseline.get("definition") or {}
            evidence[baseline_key(metric, date, int(window))] = {
                "evidence_type": "market_metric_baseline",
                "metric": metric,
                "date": date,
                "window": int(window),
                "current": baseline.get("current"),
                "avg": baseline.get("avg"),
                "median": baseline.get("median"),
                "percentile": baseline.get("percentile"),
                "sample_count": baseline.get("sample_count"),
                "complete": baseline.get("complete"),
                "unit": baseline.get("unit"),
                "source": definition.get("source"),
                "endpoint": definition.get("endpoint"),
            }

        elif record.tool == "get_index_performance":
            for quote in result.get("indices") or []:
                code = quote.get("code")
                if not code:
                    continue
                evidence[index_key(code, date)] = {
                    "evidence_type": "index_quote",
                    "index": code,
                    "date": date,
                    "close": quote.get("close"),
                    "previous_close": quote.get("previous_close"),
                    "change_pct": quote.get("change_pct"),
                    "turnover_cny": quote.get("turnover"),
                }

        elif record.tool == "get_stock_detail":
            stock = result.get("stock") or {}
            code = stock.get("code")
            if code:
                evidence[stock_key(code, date)] = {
                    "evidence_type": "stock_detail",
                    "code": code,
                    "date": date,
                    "name": stock.get("name"),
                    "close": stock.get("close"),
                    "change_pct": stock.get("change_pct"),
                }

    return {"date": date, "evidence": evidence, "sector_ranking": sector_ranking}
