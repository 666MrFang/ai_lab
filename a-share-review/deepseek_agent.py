"""DeepSeek API process adapter for runner.ExternalLLMAgent.

Protocol: reads one a-share-review-agent/v1 JSON object from stdin and writes
one review JSON object to stdout. API credentials are read only from the
DEEPSEEK_API_KEY environment variable.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

from runner.agent import ReferenceAgent


API_URL = "https://api.deepseek.com/chat/completions"


def _fail(message: str, code: int = 2) -> int:
    print(message, file=sys.stderr)
    return code


def _decode_review_content(content: str):
    """Decode one JSON object without repairing model semantics.

    Accept exact JSON, a single markdown JSON fence, or whitespace/prose around
    one JSON object. Reject multiple JSON values and trailing non-whitespace
    after a decoded object unless it is only a closing markdown fence.
    """
    text = (content or "").strip()
    if text.startswith("```"):
        first_nl = text.find("\n")
        if first_nl >= 0 and text.endswith("```"):
            text = text[first_nl + 1:-3].strip()
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        if start < 0:
            raise
        decoder = json.JSONDecoder()
        value, end = decoder.raw_decode(text[start:])
        suffix = text[start + end:].strip()
        if suffix not in ("", "```"):
            raise json.JSONDecodeError("non-JSON trailing content", text, start + end)
    if not isinstance(value, dict):
        raise ValueError("review root must be object")
    return value


def _parse_args(argv=None):
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--model", choices=("deepseek-flash", "deepseek-v4-pro"))
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = _parse_args(argv)
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        return _fail("DEEPSEEK_API_KEY is not configured")

    try:
        request_obj = json.load(sys.stdin)
    except Exception as exc:
        return _fail("invalid stdin JSON: %s" % type(exc).__name__)

    if request_obj.get("protocol") != "a-share-review-agent/v1":
        return _fail("unsupported agent protocol")

    # DeepSeek's public API currently exposes deepseek-flash and
    # deepseek-v4-pro. Keep model selection configurable but fail locally for
    # accidental unsupported aliases rather than spending an API request.
    # CLI is authoritative because review_product.py explicitly selects the
    # model. DEEPSEEK_MODEL remains a direct-adapter fallback for compatibility.
    model = args.model or os.environ.get("DEEPSEEK_MODEL", "deepseek-flash")
    if model not in {"deepseek-flash", "deepseek-v4-pro"}:
        return _fail("unsupported DeepSeek model: %s" % model)

    # Generate only the judgment layer. Deterministic facts, metric claims and
    # the closed-world evidence registry are hydrated locally after the call.
    base_review = ReferenceAgent().build_review({
        "date": request_obj["date"],
        "manifest": request_obj.get("evidence_manifest") or {},
        "normalized": request_obj.get("normalized_evidence") or {},
    })
    analysis_task = {
        "protocol": "a-share-review-analysis-patch/v1",
        "date": request_obj["date"],
        "normalized_evidence": request_obj.get("normalized_evidence") or {},
        "base_review": {
            "market_facts": base_review["market"]["facts"],
            "top_gainers": base_review["sectors"]["top_gainers"],
            "top_losers": base_review["sectors"]["top_losers"],
            "stocks": [{"code": x["code"], "name": x["name"], "sector_name": x["sector_name"],
                        "roles": x["roles"]} for x in base_review["stocks"][:12]],
        },
        "output_contract": {
            "market_inferences": "array max4: claim/confidence/evidence_gaps",
            "theme_candidates": "array max3: sector_name/confidence/reason/evidence_gaps",
            "stock_insights": "array max8: code/driver/confidence/evidence_gaps; omit without driver",
            "profit_effect": "summary/confidence/evidence_gaps",
            "loss_effect": "summary/confidence/evidence_gaps",
            "tomorrow_watch": "array max5: target/condition/meaning",
            "evidence_gaps": "string array max8",
        },
    }
    system = (
        "You are the judgment layer of an A-share daily review. Deterministic code hydrates facts "
        "and numeric tables. Do NOT reproduce raw facts, numeric tables, metric_claims, evidence_registry, "
        "schema, or source payloads. Use only supplied evidence. Produce compact investment synthesis: "
        "market structure, profit/loss effect, persistent-theme candidates versus one-day movers, stock "
        "driver hypotheses, and tomorrow strengthen/falsify conditions. News timing alone is not causality. "
        "Do not invent numeric values. Shared gaps appear once at root. Return exactly one JSON object "
        "containing only keys in output_contract."
    )
    user = json.dumps(analysis_task, ensure_ascii=False, separators=(",", ":"))
    body = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "response_format": {"type": "json_object"},
        "stream": False,
        "max_tokens": int(os.environ.get("DEEPSEEK_MAX_TOKENS", "24000")),
    }, ensure_ascii=False).encode("utf-8")

    req = urllib.request.Request(
        API_URL, data=body, method="POST",
        headers={
            "Authorization": "Bearer " + api_key,
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=int(os.environ.get("DEEPSEEK_HTTP_TIMEOUT", "110"))) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:1000]
        return _fail("DeepSeek HTTP %s: %s" % (exc.code, detail), 3)
    except Exception as exc:
        return _fail("DeepSeek request failed: %s" % type(exc).__name__, 4)

    try:
        content = payload["choices"][0]["message"]["content"]
        patch = _decode_review_content(content)
        review = base_review
        def _ev(statement):
            return {"statement": statement, "source": "evidence_store", "strength": "MEDIUM"}
        review["market"]["inferences"] = [{
            "claim": x.get("claim", ""), "confidence": x.get("confidence", "LOW"),
            "evidence": [_ev("synthesis from stored evidence")], "counter_evidence": [],
            "evidence_gaps": x.get("evidence_gaps") or [], "causal_status": None,
            "causal_evidence_refs": [],
        } for x in (patch.get("market_inferences") or [])[:4] if x.get("claim")]
        review["sectors"]["main_theme_candidates"] = [{
            "sector_name": x.get("sector_name", "UNKNOWN"), "confidence": x.get("confidence", "LOW"),
            "evidence": [_ev(x.get("reason") or "candidate synthesized from stored evidence")],
            "evidence_gaps": x.get("evidence_gaps") or [],
        } for x in (patch.get("theme_candidates") or [])[:3] if x.get("sector_name")]
        insights = {str(x.get("code")): x for x in (patch.get("stock_insights") or [])[:8] if x.get("code")}
        for stock in review["stocks"]:
            insight = insights.get(str(stock.get("code")))
            if insight and insight.get("driver"):
                stock["possible_drivers"] = [{
                    "claim": insight["driver"], "confidence": insight.get("confidence", "LOW"),
                    "evidence": [_ev("driver hypothesis synthesized from stored evidence")],
                    "counter_evidence": [], "evidence_gaps": insight.get("evidence_gaps") or [],
                    "causal_status": "HYPOTHESIS", "causal_evidence_refs": [],
                }]
        for key in ("profit_effect", "loss_effect"):
            value = patch.get(key) or {}
            if value.get("summary"):
                review[key] = {"summary": value["summary"], "confidence": value.get("confidence", "LOW"),
                               "evidence": [_ev("synthesis from stored evidence")],
                               "evidence_gaps": value.get("evidence_gaps") or []}
        review["tomorrow_watch_conditions"] = [{
            "target": x.get("target", ""), "condition": x.get("condition", ""),
            "meaning": x.get("meaning", ""), "condition_id": None, "metric": None,
            "operator": None, "expected_value": None, "horizon_sessions": 1,
            "evidence_ref": None,
        } for x in (patch.get("tomorrow_watch") or [])[:5]
          if x.get("target") and x.get("condition") and x.get("meaning")]
        review["evidence_gaps"] = list(dict.fromkeys((patch.get("evidence_gaps") or [])[:8]))
    except Exception as exc:
        # Include only shape/length diagnostics; never echo provider content,
        # because generated text may contain evidence or unexpected material.
        content_len = len(content) if isinstance(locals().get("content"), str) else -1
        finish = ((payload.get("choices") or [{}])[0].get("finish_reason")
                  if isinstance(payload, dict) else None)
        reason = "OUTPUT_TRUNCATED" if finish == "length" else "INVALID_JSON"
        return _fail(
            "DeepSeek response is not valid review JSON: %s; content_len=%s; finish_reason=%s; reason=%s"
            % (type(exc).__name__, content_len, finish, reason), 5
        )

    # stdout is deliberately review JSON only: the parent adapter persists raw
    # execution metadata separately and the existing Runner validates this object.
    sys.stdout.write(json.dumps(review, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
