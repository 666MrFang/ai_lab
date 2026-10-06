"""Breadth / limit-ecology metric definitions (source of truth).

Definitions are derived from **verified live payload behaviour** (Round 2A
probe), never from vendor docstrings. Two verified facts to remember:

- ``stock_zt_pool_em``'s docstring claims ST *and* STAR (688) stocks are
  excluded, but the live payload includes 688 codes and excludes ST names.
  The payload wins.
- ``stock_market_activity_legu`` uses a *different* universe for ``涨停`` than
  the Eastmoney limit pools, so the two must never be mixed.

This module is pure data (no provider imports) so it can be imported by the
domain layer and tests without side effects.
"""

from __future__ import annotations

from typing import Dict, Tuple

from domain.models import MetricDefinition

_EASTMONEY_LIMIT_UNIVERSE = (
    "Eastmoney 涨停板行情股池。已验证：payload 含 688 科创板代码、不含 ST 名称；"
    "vendor docstring 声称排除科创板，但被 payload 反证。"
)

METRIC_DEFINITIONS: Dict[str, MetricDefinition] = {
    "limit_up_count": MetricDefinition(
        metric="limit_up_count",
        source="eastmoney",
        endpoint="stock_zt_pool_em",
        unit="count",
        universe_definition=_EASTMONEY_LIMIT_UNIVERSE,
        date_semantics="交易日 D 收盘涨停股池",
        historical=True,
    ),
    "limit_down_count": MetricDefinition(
        metric="limit_down_count",
        source="eastmoney",
        endpoint="stock_zt_pool_dtgc_em",
        unit="count",
        universe_definition="Eastmoney 跌停股池：当日当前跌停的全部 A 股。",
        date_semantics="交易日 D 收盘跌停股池（AkShare 侧限制最近 30 个自然日）",
        historical=True,
    ),
    "broken_limit_count": MetricDefinition(
        metric="broken_limit_count",
        source="eastmoney",
        endpoint="stock_zt_pool_zbgc_em",
        unit="count",
        universe_definition="Eastmoney 炸板股池：当日触及涨停但当前未封板的 A 股。",
        date_semantics="交易日 D 炸板股池（AkShare 侧限制最近 30 个自然日）",
        historical=True,
    ),
    "broken_limit_rate": MetricDefinition(
        metric="broken_limit_rate",
        source="eastmoney",
        endpoint="stock_zt_pool_zbgc_em+stock_zt_pool_em",
        unit="percent",
        universe_definition=(
            "衍生指标：broken_limit_count / (broken_limit_count + limit_up_count)"
            " * 100；分母为 0 时返回 None，绝不填 0。"
        ),
        date_semantics="交易日 D（两个股池同源、同 universe）",
        historical=True,
    ),
    "first_limit_up_count": MetricDefinition(
        metric="first_limit_up_count",
        source="eastmoney",
        endpoint="stock_zt_pool_em",
        unit="count",
        universe_definition=_EASTMONEY_LIMIT_UNIVERSE + " 首板定义：连板数 == 1。",
        date_semantics="交易日 D",
        historical=True,
    ),
    "multi_limit_up_count": MetricDefinition(
        metric="multi_limit_up_count",
        source="eastmoney",
        endpoint="stock_zt_pool_em",
        unit="count",
        universe_definition=_EASTMONEY_LIMIT_UNIVERSE + " 连板定义：连板数 >= 2。",
        date_semantics="交易日 D",
        historical=True,
    ),
    "max_consecutive_limit_up": MetricDefinition(
        metric="max_consecutive_limit_up",
        source="eastmoney",
        endpoint="stock_zt_pool_em",
        unit="count",
        universe_definition=_EASTMONEY_LIMIT_UNIVERSE + " 最大连板数 = max(连板数)。",
        date_semantics="交易日 D",
        historical=True,
    ),
    "previous_limit_up_sample_size": MetricDefinition(
        metric="previous_limit_up_sample_size",
        source="eastmoney",
        endpoint="stock_zt_pool_previous_em",
        unit="count",
        universe_definition=(
            "Eastmoney 昨日涨停股池：上一交易日收盘涨停的 A 股，用交易日 D 的价格评估。"
            "已验证 prev(D) 与 zt(D-1) 代码基本一致。"
        ),
        date_semantics="前一交易日涨停、交易日 D 表现",
        historical=True,
    ),
    "previous_limit_up_average_change_pct": MetricDefinition(
        metric="previous_limit_up_average_change_pct",
        source="eastmoney",
        endpoint="stock_zt_pool_previous_em",
        unit="percent",
        universe_definition="昨日涨停股池在交易日 D 的涨跌幅均值。",
        date_semantics="交易日 D",
        historical=True,
    ),
    "previous_limit_up_median_change_pct": MetricDefinition(
        metric="previous_limit_up_median_change_pct",
        source="eastmoney",
        endpoint="stock_zt_pool_previous_em",
        unit="percent",
        universe_definition="昨日涨停股池在交易日 D 的涨跌幅中位数。",
        date_semantics="交易日 D",
        historical=True,
    ),
    "previous_limit_up_positive_rate": MetricDefinition(
        metric="previous_limit_up_positive_rate",
        source="eastmoney",
        endpoint="stock_zt_pool_previous_em",
        unit="percent",
        universe_definition=(
            "昨日涨停股池在交易日 D 上涨占比：涨跌幅 > 0 严格判定；"
            "涨跌幅 == 0 不计入 positive。"
        ),
        date_semantics="交易日 D",
        historical=True,
    ),
    "promotion_rate": MetricDefinition(
        metric="promotion_rate",
        source="eastmoney",
        endpoint="stock_zt_pool_previous_em+stock_zt_pool_em",
        unit="percent",
        universe_definition=(
            "衍生指标：prev(D) ∩ limit_up(D) 的数量 / prev(D) sample_size * 100；"
            "sample_size 为 0 时返回 None。"
        ),
        date_semantics="交易日 D",
        historical=True,
    ),
    "advance_count": MetricDefinition(
        metric="advance_count",
        source="legulegu",
        endpoint="stock_market_activity_legu",
        unit="count",
        universe_definition="乐咕乐股网赚钱效应快照：item `上涨`。CURRENT_ONLY。",
        date_semantics="页面统计日期（最近一个已完成交易日，通常仅当日可用）",
        historical=False,
    ),
    "decline_count": MetricDefinition(
        metric="decline_count",
        source="legulegu",
        endpoint="stock_market_activity_legu",
        unit="count",
        universe_definition="乐咕乐股网赚钱效应快照：item `下跌`。CURRENT_ONLY。",
        date_semantics="页面统计日期（CURRENT_ONLY）",
        historical=False,
    ),
    "flat_count": MetricDefinition(
        metric="flat_count",
        source="legulegu",
        endpoint="stock_market_activity_legu",
        unit="count",
        universe_definition="乐咕乐股网赚钱效应快照：item `平盘`。CURRENT_ONLY。",
        date_semantics="页面统计日期（CURRENT_ONLY）",
        historical=False,
    ),
}

# Metrics supported by get_market_metric_baseline (Round 2B first batch).
SUPPORTED_BASELINE_METRICS: Tuple[str, ...] = (
    "limit_up_count",
    "limit_down_count",
    "broken_limit_count",
    "broken_limit_rate",
    "first_limit_up_count",
    "multi_limit_up_count",
    "max_consecutive_limit_up",
    "promotion_rate",
    "previous_limit_up_positive_rate",
)
