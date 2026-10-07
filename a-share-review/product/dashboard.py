"""Zero-dependency HTML dashboard for one completed review day."""

from __future__ import annotations

from html import escape
from typing import Any, Dict


def _pct(value: Any) -> str:
    return "—" if value is None else ("%.2f%%" % float(value))


def _money(value: Any) -> str:
    if value is None:
        return "—"
    value = float(value)
    if abs(value) >= 100_000_000:
        return "%.2f亿" % (value / 100_000_000)
    if abs(value) >= 10_000:
        return "%.2f万" % (value / 10_000)
    return "%.0f" % value


def _stock_fact_groups(stock: Dict[str, Any]) -> tuple[str, str, str]:
    market, news, disclosures = [], [], []
    for fact in stock.get("facts") or []:
        statement = escape(str(fact.get("statement", "")))
        if statement.startswith("公司公告"):
            disclosures.append(statement)
        elif statement.startswith("新闻"):
            news.append(statement)
        else:
            market.append(statement)
    return ("<br>".join(market[:4]), "<br>".join(news[:3]),
            "<br>".join(disclosures[:3]))


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
    stock_rows_parts = []
    for x in review.get("stocks") or []:
        market_facts, news_facts, disclosure_facts = _stock_fact_groups(x)
        stock_rows_parts.append(
            "<tr><td><b>%s</b><br><small>%s</small></td><td>%s</td><td>%s</td>"
            "<td>%s</td><td>%s</td><td>%s</td></tr>" % (
                escape(str(x.get("name", "—"))), escape(str(x.get("code", "—"))),
                escape(str(x.get("sector_name", "—"))),
                escape(" / ".join(x.get("roles") or ["OTHER"])),
                market_facts or "—", news_facts or "—", disclosure_facts or "—",
            )
        )
    stock_rows = "".join(stock_rows_parts)
    gainers = (review.get("sectors") or {}).get("top_gainers") or []
    losers = (review.get("sectors") or {}).get("top_losers") or []
    sector_detail_rows = "".join(
        "<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>" % (
            escape(str(x.get("sector_name") or "—")), _pct(x.get("change_pct")),
            _pct(x.get("change_5d_pct")), _pct(x.get("change_20d_pct")),
            _money(x.get("turnover_cny")),
        ) for x in gainers + losers
    )
    status = escape(str(memory_record.get("status", "OPEN")))
    verification = memory_record.get("d1_verification") or {}
    verification_rows = "".join(
        "<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>" % (
            escape(str(x.get("metric") or "—")),
            escape(str(x.get("expected_value") if x.get("expected_value") is not None else "—")),
            escape(str(x.get("actual_value") if x.get("actual_value") is not None else "—")),
            escape(str(x.get("status") or "NOT_OBSERVABLE")),
        )
        for x in verification.get("results") or []
    )
    if not verification_rows:
        verification_rows = "<tr><td colspan='4'>尚无 D+1 可验证结果</td></tr>"
    return """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>A股复盘 %s</title>
<style>
body{font-family:system-ui,-apple-system,"Microsoft YaHei",sans-serif;max-width:1280px;margin:32px auto;padding:0 20px;background:#f6f7f9;color:#1f2937}
.card{background:white;border-radius:12px;padding:20px;margin:14px 0;box-shadow:0 1px 4px #0001;overflow-x:auto}
h1,h2{margin-top:0} h2{font-size:18px} table{width:100%%;border-collapse:collapse}td,th{padding:10px;border-bottom:1px solid #eee;text-align:left;vertical-align:top}
.badge{display:inline-block;padding:4px 9px;border-radius:999px;background:#eef2ff;margin-right:8px}
small{color:#6b7280}.warn{background:#fff7ed}.secondary{opacity:.82}.section-note{margin-top:-8px;color:#6b7280}
</style></head><body>
<h1>A股盘后复盘 · %s</h1>
<div class="card"><span class="badge">Regime %s</span><span class="badge">Confidence %s</span><span class="badge">Memory %s</span></div>
<div class="card"><h2>① 市场温度</h2><div class="section-note">指数、量能、市场宽度与情绪事实</div><ul>%s</ul></div>
<div class="card"><h2>② 强弱行业</h2><div class="section-note">当日强弱 + 5D/20D 持续性 + 成交额</div><table><thead><tr><th>板块</th><th>当日</th><th>5D</th><th>20D</th><th>成交额(元)</th></tr></thead><tbody>%s</tbody></table></div>
<div class="card secondary"><h2>历史相似场景</h2><table><thead><tr><th>板块</th><th>当日</th><th>历史相似场景</th></tr></thead><tbody>%s</tbody></table></div>
<div class="card"><h2>③ 核心个股与事件</h2><div class="section-note">强势股 / 涨停连板核心候选 / 容量候选，以及行情事实、媒体新闻和正式公告三类独立 Evidence</div><table><thead><tr><th>股票</th><th>板块</th><th>角色</th><th>行情 / 历史</th><th>新闻</th><th>公司公告</th></tr></thead><tbody>%s</tbody></table><small>LIMIT_UP_CORE_CANDIDATE 仅表示当日涨停/连板短线核心候选；CAPACITY_CORE_CANDIDATE 仅表示市值候选；二者都不等同于龙头确认。</small></div>
<div class="card"><h2>④ 明日观察与验证</h2><ul>%s</ul></div>
<div class="card secondary"><h2>D+1 自动回验</h2><table><thead><tr><th>指标</th><th>条件值</th><th>实际值</th><th>结果</th></tr></thead><tbody>%s</tbody></table><small>NOT_OBSERVABLE 既不计为通过，也不计为失败。</small></div>
<div class="card warn"><h2>⑤ Evidence Gap</h2><ul>%s</ul><small>Historical Pattern ≠ Future Fact；样本不足时不会生成概率性结论。</small></div>
</body></html>""" % (
        date, date, escape(str(regime.get("state", "UNCERTAIN"))),
        escape(str(regime.get("confidence", "LOW"))), status, facts,
        sector_detail_rows, "".join(sector_rows), stock_rows, watch, verification_rows, gaps,
    )
