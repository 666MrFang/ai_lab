"""Round 5A — Sector data capability probe (read-only).

Probes AkShare sector sources (THS / Eastmoney / Sina / SW) and records the
actual payload shape, units, taxonomy, historical support and failure modes.

Writes a machine-readable dump to ``output/sector-probe/probe.json`` and prints
a compact matrix. This script does NOT modify any production code.

    python scripts/probe_sector_sources.py
"""

from __future__ import annotations

import datetime as dt
import json
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

import akshare as ak  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "output" / "sector-probe"

NETWORK_KEYWORDS = (
    "max retries", "connection", "timed out", "timeout", "proxy", "ssl",
    "getaddrinfo", "remote end closed", "connectionpool", "failed to establish",
    "read timed out", "network is unreachable",
)


def classify(exc: Exception) -> str:
    text = f"{type(exc).__name__} {exc}".lower()
    if any(k in text for k in NETWORK_KEYWORDS):
        return "NETWORK_ERROR"
    if "not support" in text or "unsupported" in text:
        return "UNSUPPORTED"
    return "UNKNOWN"


def probe(category: str, taxonomy: str, label: str, fn) -> dict:
    record = {
        "label": label,
        "category": category,
        "taxonomy": taxonomy,
        "status": "UNKNOWN",
        "rows": 0,
        "columns": [],
        "dtypes": {},
        "sample": [],
    }
    try:
        frame = fn()
        if frame is None:
            record["status"] = "EMPTY"
            return record
        if hasattr(frame, "empty") and frame.empty:
            record["status"] = "EMPTY"
            record["columns"] = [str(c) for c in frame.columns]
            return record
        record["status"] = "AVAILABLE"
        record["rows"] = int(len(frame))
        record["columns"] = [str(c) for c in frame.columns]
        record["dtypes"] = {str(c): str(t) for c, t in frame.dtypes.items()}
        record["sample"] = json.loads(frame.head(2).to_json(orient="records", force_ascii=False))
    except Exception as exc:  # noqa: BLE001
        record["status"] = classify(exc)
        record["error"] = f"{type(exc).__name__}: {str(exc)[:160]}"
    return record


def build_probes() -> list:
    P = []
    # --- Eastmoney ranking ---
    P.append(probe("ranking", "unknown", "stock_board_industry_name_em", ak.stock_board_industry_name_em))
    P.append(probe("ranking", "unknown", "stock_board_concept_name_em", ak.stock_board_concept_name_em))
    # --- Eastmoney constituents ---
    P.append(probe("constituents", "industry", "stock_board_industry_cons_em(半导体)", lambda: ak.stock_board_industry_cons_em(symbol="半导体")))
    P.append(probe("constituents", "concept", "stock_board_concept_cons_em(人工智能)", lambda: ak.stock_board_concept_cons_em(symbol="人工智能")))
    # --- Eastmoney history ---
    P.append(probe("history", "industry", "stock_board_industry_hist_em(半导体)", lambda: ak.stock_board_industry_hist_em(symbol="半导体", start_date="20260901", end_date="20260930", period="日k", adjust="")))
    # --- THS taxonomy ---
    P.append(probe("taxonomy", "industry", "stock_board_industry_name_ths", ak.stock_board_industry_name_ths))
    P.append(probe("taxonomy", "concept", "stock_board_concept_name_ths", ak.stock_board_concept_name_ths))
    # --- THS ranking / snapshot ---
    P.append(probe("ranking", "industry", "stock_board_industry_summary_ths", ak.stock_board_industry_summary_ths))
    P.append(probe("ranking", "concept", "stock_board_concept_summary_ths", ak.stock_board_concept_summary_ths))
    # --- THS history ---
    P.append(probe("history", "industry", "stock_board_industry_index_ths(半导体,2026-09-01..30)", lambda: ak.stock_board_industry_index_ths(symbol="半导体", start_date="20260901", end_date="20260930")))
    P.append(probe("history", "concept", "stock_board_concept_index_ths(人工智能,2026-09-01..30)", lambda: ak.stock_board_concept_index_ths(symbol="人工智能", start_date="20260901", end_date="20260930")))
    # --- THS info (constituents?) ---
    P.append(probe("constituents", "industry", "stock_board_industry_info_ths(881121)", lambda: ak.stock_board_industry_info_ths(symbol="881121")))
    P.append(probe("constituents", "concept", "stock_board_concept_info_ths(308614)", lambda: ak.stock_board_concept_info_ths(symbol="308614")))
    # --- Sina sector ---
    P.append(probe("ranking", "industry", "stock_sector_spot(新浪行业)", lambda: ak.stock_sector_spot(indicator="新浪行业")))
    P.append(probe("ranking", "concept", "stock_sector_spot(概念)", lambda: ak.stock_sector_spot(indicator="概念")))
    # --- SW index ---
    P.append(probe("taxonomy", "industry", "sw_index_first_info", ak.sw_index_first_info))
    P.append(probe("taxonomy", "industry", "sw_index_second_info", ak.sw_index_second_info))
    # --- Fund flow ranking ---
    P.append(probe("ranking", "industry", "stock_sector_fund_flow_rank(行业)", lambda: ak.stock_sector_fund_flow_rank(indicator="今日", sector_type="行业资金流")))
    P.append(probe("ranking", "concept", "stock_sector_fund_flow_rank(概念)", lambda: ak.stock_sector_fund_flow_rank(indicator="今日", sector_type="概念资金流")))
    # --- Index constituents ---
    P.append(probe("constituents", "index", "index_stock_cons(000300)", lambda: ak.index_stock_cons(symbol="000300")))
    # --- Sina constituents (with mktcap/nmc) ---
    P.append(probe("constituents", "industry", "stock_sector_detail(sina-industry)",
                   lambda: ak.stock_sector_detail(sector=ak.stock_sector_spot(indicator="新浪行业")["label"].iloc[0])))
    P.append(probe("constituents", "concept", "stock_sector_detail(sina-concept)",
                   lambda: ak.stock_sector_detail(sector=ak.stock_sector_spot(indicator="概念")["label"].iloc[0])))
    # --- SW constituents (with 市值 + 1d/5d) ---
    P.append(probe("constituents", "industry", "sw_index_third_cons(801016.SI)",
                   lambda: ak.sw_index_third_cons(symbol="801016.SI")))
    # --- THS fund-flow rankings ---
    P.append(probe("ranking", "industry", "stock_fund_flow_industry(即时)",
                   lambda: ak.stock_fund_flow_industry(symbol="即时")))
    P.append(probe("ranking", "concept", "stock_fund_flow_concept(即时)",
                   lambda: ak.stock_fund_flow_concept(symbol="即时")))
    return P


SIGNATURE_TARGETS = [
    "stock_sector_spot", "stock_sector_detail", "stock_board_industry_summary_ths",
    "stock_board_concept_summary_ths", "stock_board_industry_index_ths",
    "stock_board_industry_name_ths", "stock_board_concept_name_ths",
    "sw_index_third_cons", "stock_fund_flow_industry", "stock_fund_flow_concept",
]


def signatures() -> dict:
    import inspect
    out = {}
    for name in SIGNATURE_TARGETS:
        try:
            out[name] = str(inspect.signature(getattr(ak, name)))
        except Exception as exc:  # noqa: BLE001
            out[name] = "ERR %s" % type(exc).__name__
    return out


def main() -> int:
    print("AKSHARE_VERSION=%s" % getattr(ak, "__version__", "?"))
    print("PROBED_AT=%s" % dt.datetime.now().isoformat(timespec="seconds"))
    sig = signatures()
    for name, value in sig.items():
        print("SIG|%s|%s" % (name, value))
    results = build_probes()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "probe.json").write_text(
        json.dumps({"signatures": sig, "probes": results}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    for record in results:
        print("PROBE|%s|%s|%s|rows=%d|status=%s" % (
            record["category"], record["taxonomy"], record["label"],
            record["rows"], record["status"]))
        if record["status"] == "AVAILABLE":
            print("  cols=%s" % ",".join(record["columns"]))
            print("  dtypes=%s" % json.dumps(record["dtypes"], ensure_ascii=False))
            print("  sample=%s" % json.dumps(record["sample"], ensure_ascii=False)[:600])
        elif record.get("error"):
            print("  error=%s" % record["error"])
    print("SAVED|%s" % (OUT / "probe.json"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
