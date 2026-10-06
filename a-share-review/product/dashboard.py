"""Zero-dependency HTML dashboard for one completed review day."""

from __future__ import annotations

from html import escape
from typing import Any, Dict


def _pct(value: Any) -> str:
    return "—" if value is None else ("%.2f%%" % float(value))


def render_dashboard(
    review: Dict[str, Any],
    outlook: Dict[str, Any],
    memory_record: Dict[str, Any],
) -> str:
    date = escape(str(review.get("date", "")))
    regime = review.get("market_regime") or {}
    sector_rows = []
    for item in outlook.get("patterns") or []:
        stats = (item.get("statistics") or {}).get("t1") or {}
        if stats.get("status") == "CALIBRATED":
            history = "T+1: 样本 %s，上涨 %.1f%%，均值 %s，中位数 %s" % (
                stats.get("sample_size"), stats.get("positive_rate"),
                _pct(stats.get("average_return_pct")), _pct(stats.get("median_return_pct")),
            )
        else:
            history = "T+1: 历史样本不足（%s/%s）" % (
                stats.get("sample_size", 0), stats.get("minimum_sample", 8)
            )
        sector_rows.append(
            "<tr><td>%s</td><td>%s</td><td>%s</td></tr>" % (
                escape(str(item.get("sector_name") or "—")),
                _pct((item.get("current_state") or {}).get("sector_change_pct")),
                escape(history),
            )
        )

    facts = "".join(
        "<li>%s</li>" % escape(str(x.get("statement", "")))
        for x in (review.get("market") or {}).get("facts") or []
    )
    gaps = "".join(
        "<li>%s</li>" % escape(str(x))
        for x in review.get("evidence_gaps") or []
    )
    watch = "".join(
        "<li><b>%s</b>：%s<br><small>%s</small></li>" % (
            escape(str(x.get("target", ""))),
            escape(str(x.get("condition", ""))),
            escape(str(x.get("meaning", ""))),
        )
        for x in review.get("tomorrow_watch_conditions") or []
    )
    status = escape(str(memory_record.get("status", "OPEN")))
    return """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>A股复盘 %s</title>
<style>
body{font-family:system-ui,-apple-system,"Microsoft YaHei",sans-serif;max-width:1100px;margin:36px auto;padding:0 20px;background:#f6f7f9;color:#1f2937}
.card{background:white;border-radius:12px;padding:20px;margin:14px 0;box-shadow:0 1px 4px #0001}
h1,h2{margin-top:0} table{width:100%%;border-collapse:collapse}td,th{padding:10px;border-bottom:1px solid #eee;text-align:left}
.badge{display:inline-block;padding:4px 9px;border-radius:999px;background:#eef2ff;margin-right:8px}
small{color:#6b7280}.warn{background:#fff7ed}
</style></head><body>
<h1>A股盘后复盘 · %s</h1>
<div class="card"><span class="badge">Regime %s</span><span class="badge">Confidence %s</span><span class="badge">Memory %s</span></div>
<div class="card"><h2>市场事实</h2><ul>%s</ul></div>
<div class="card"><h2>强势板块与历史反馈</h2><table><thead><tr><th>板块</th><th>当日</th><th>历史相似场景</th></tr></thead><tbody>%s</tbody></table></div>
<div class="card"><h2>明日验证条件</h2><ul>%s</ul></div>
<div class="card warn"><h2>证据缺口</h2><ul>%s</ul><small>Historical Pattern ≠ Future Fact；样本不足时不会生成概率性结论。</small></div>
</body></html>""" % (
        date, date, escape(str(regime.get("state", "UNCERTAIN"))),
        escape(str(regime.get("confidence", "LOW"))), status, facts,
        "".join(sector_rows), watch, gaps,
    )
