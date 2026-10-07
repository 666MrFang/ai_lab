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

    system = (
        "You are the generator inside an independently evaluated A-share daily-review "
        "pipeline. Use ONLY the supplied evidence. Follow the supplied Skill and JSON "
        "Schema. Do not use outside market knowledge. Do not infer causality from news "
        "existence. Evidence gaps must remain explicit. The supplied allowed_evidence_registry "
        "is CLOSED-WORLD: copy only exact entries from it into evidence_registry and reference "
        "their evidence_id values; never invent, rename, aggregate, or reconstruct evidence. "
        "Index quotes outside that registry may be stated as facts from normalized_evidence but "
        "must not be converted into invented metric_claims/evidence_registry entries. "
        "For stock possible_drivers, set causal_status to HYPOTHESIS or UNSUPPORTED unless "
        "the supplied evidence explicitly establishes causality. SUPPORTED requires non-empty "
        "causal_evidence_refs; news existence or timing alone is not causal proof. "
        "Be concise: include only evidence needed for the review; do not repeat the same fact "
        "across sections unless the schema requires it; keep evidence_gaps deduplicated; limit "
        "market facts/inferences, theme candidates, stock facts/drivers, and watch conditions to "
        "the smallest useful set supported by evidence. Copy evidence_registry entries only when "
        "actually referenced by metric_claims. Return exactly one JSON object matching the schema; "
        "no markdown fences and no prose outside JSON."
    )
    user = json.dumps(request_obj, ensure_ascii=False, separators=(",", ":"))
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
        review = _decode_review_content(content)
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
