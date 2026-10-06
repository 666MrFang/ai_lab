import json
import sys
from pathlib import Path
from typing import Any

from mcp.server import MCPServer

from config import DATA_MODE_MOCK, DATA_MODE_REAL, load_settings

# Runtime identity: surfaced via the MCP handshake (serverInfo.version) and a
# non-invasive stderr startup log so a live instance can be told apart from a
# stale one. It never alters any tool contract.
MARKET_MCP_BUILD = "product-v13-akshare-real"
from domain.reference import TOTAL_TURNOVER_CODES
from errors import ErrorCode, MarketError, error_payload
from routing import config_mode_error, unimplemented_error
from service import MarketService


# ============================================================
# MCP Server
# ============================================================

mcp = MCPServer("A-Share Market MCP", version=MARKET_MCP_BUILD)


# ============================================================
# Data / service
# ============================================================

DATA_FILE = Path(__file__).parent / "data" / "mock_market.json"

SETTINGS = load_settings()
SERVICE = MarketService(SETTINGS)

RUNTIME_PROVIDER = "akshare" if SETTINGS.data_mode == DATA_MODE_REAL else "mock"
sys.stderr.write(
    "[market-mcp][startup] build=%s provider=%s data_mode=%s python=%s\n"
    % (MARKET_MCP_BUILD, RUNTIME_PROVIDER, SETTINGS.data_mode, sys.version.split()[0])
)
sys.stderr.flush()

TOTAL_TURNOVER_INDEX_CODES = TOTAL_TURNOVER_CODES


def load_market_data() -> dict[str, Any]:
    """Load mock A-share market data (mock mode only)."""

    with DATA_FILE.open("r", encoding="utf-8") as f:
        return json.load(f)


# ============================================================
# Tools
# ============================================================

@mcp.tool()
def get_index_performance(date: str) -> dict[str, Any]:
    """
    获取指定交易日期的 A 股主要市场指数行情，
    包括开盘、前收盘、收盘、涨跌幅和成交额。

    用于分析当日 A 股大盘整体表现。
    不提供行业板块或个股行情。

    Args:
        date: 交易日期，格式 YYYY-MM-DD。
    """

    mode_error = config_mode_error(SETTINGS)
    if mode_error is not None:
        return mode_error

    if SETTINGS.data_mode == DATA_MODE_MOCK:
        market_data = load_market_data()

        if date not in market_data:
            return {
                "success": False,
                "date": date,
                "error": "market data not found"
            }

        return {
            "success": True,
            "date": date,
            "indices": market_data[date]["indices"]
        }

    try:
        quotes = SERVICE.get_index_performance(date)
    except MarketError as exc:
        return error_payload(exc.error_code, exc.message, date=date)

    return {
        "success": True,
        "date": date,
        "indices": [quote.to_tool_dict() for quote in quotes]
    }


@mcp.tool()
def get_sector_ranking(
    date: str,
    direction: str = "gainers",
    limit: int = 10
) -> dict[str, Any]:
    """
    获取指定交易日期 A 股板块按涨跌幅的排名。

    direction="gainers"（默认）：按 change_pct 从高到低返回。
    direction="losers"：按 change_pct 从低到高返回。

    用于识别当日领涨和领跌板块。
    当需要比较不同板块的强弱、找出涨幅居前或跌幅居后的板块时调用。

    不用于获取单个板块的详细成分股（请使用 get_sector_detail），
    也不用于获取大盘指数行情（请使用 get_index_performance）。

    Args:
        date: 交易日期，格式 YYYY-MM-DD。
        direction: "gainers" 或 "losers"，默认 "gainers"。
        limit: 返回的板块数量，必须为正整数，默认 10。

    返回字段：
        change_pct: 百分比。
        turnover_cny: 成交额，单位人民币元。
        turnover: 兼容旧调用保留的字段，与 turnover_cny 数值、单位相同。
    """

    mode_error = config_mode_error(SETTINGS)
    if mode_error is not None:
        return mode_error

    if SETTINGS.data_mode == DATA_MODE_REAL:
        try:
            sectors = SERVICE.get_sector_ranking(date, direction, limit)
        except MarketError as exc:
            return error_payload(
                exc.error_code, exc.message, date=date, direction=direction
            )
        return {
            "success": True,
            "date": date,
            "direction": direction,
            "count": len(sectors),
            "sectors": [snapshot.to_tool_dict() for snapshot in sectors],
        }

    if direction not in ("gainers", "losers"):
        return {
            "success": False,
            "date": date,
            "direction": direction,
            "error": "direction must be 'gainers' or 'losers'"
        }

    market_data = load_market_data()

    if date not in market_data:
        return {
            "success": False,
            "date": date,
            "direction": direction,
            "error": "market data not found"
        }

    sectors = market_data[date].get("sectors")
    if sectors is None:
        return {
            "success": False,
            "date": date,
            "direction": direction,
            "error": "sector data not found"
        }

    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
        return {
            "success": False,
            "date": date,
            "direction": direction,
            "error": "limit must be a positive integer",
            "limit": limit
        }

    reverse = direction == "gainers"
    ranking = sorted(sectors, key=lambda item: item["change_pct"], reverse=reverse)

    return {
        "success": True,
        "date": date,
        "direction": direction,
        "count": len(ranking[:limit]),
        "sectors": [
            {
                "sector_name": item["sector_name"],
                "change_pct": item["change_pct"],
                "turnover": item["turnover"],
                "turnover_cny": item["turnover"]
            }
            for item in ranking[:limit]
        ]
    }


@mcp.tool()
def get_sector_history_summary(date: str, sector_name: str) -> dict[str, Any]:
    """
    获取指定交易日期某行业板块的 5 日 / 20 日历史表现与成交额基准。

    数据来源为 THS 行业指数历史（source_family="ths"）。仅返回数值事实，
    不做“主线/龙头”判断，不输出未来预测。

    5d = current session + previous 4 completed sessions；
    20d = current session + previous 19 completed sessions。
    complete=false 时对应统计为 null（不得用于语义推断）。

    Args:
        date: 交易日期，格式 YYYY-MM-DD（通常是最近已完成交易日）。
        sector_name: THS 行业名称，例如 半导体。
    """

    mode_error = config_mode_error(SETTINGS)
    if mode_error is not None:
        return mode_error

    if SETTINGS.data_mode != DATA_MODE_REAL:
        return error_payload(
            ErrorCode.MOCK_NOT_SUPPORTED,
            "get_sector_history_summary is only available with real market data",
            date=date,
            sector_name=sector_name,
        )

    try:
        summary = SERVICE.get_sector_history_summary(date, sector_name)
    except MarketError as exc:
        return error_payload(
            exc.error_code, exc.message, date=date, sector_name=sector_name
        )

    return {
        "success": True,
        "date": date,
        "sector_name": sector_name,
        **summary.to_tool_dict(),
    }


@mcp.tool()
def get_sector_membership(sector_name: str) -> dict[str, Any]:
    """
    获取某行业板块的当前成分股（独立 Membership Family，source_family="sina"）。

    这是 CURRENT_MEMBERSHIP_ONLY 的独立证据，不是 THS 板块成分：
    不得与 THS ranking 混合计算“板块内部广度 / 贡献度 / 龙头”。
    仅当存在 VERIFIED 的 THS→Sina 映射时返回；否则
    SECTOR_MEMBERSHIP_UNAVAILABLE。

    Args:
        sector_name: THS 行业名称，例如 半导体。
    """

    mode_error = config_mode_error(SETTINGS)
    if mode_error is not None:
        return mode_error

    if SETTINGS.data_mode != DATA_MODE_REAL:
        return error_payload(
            ErrorCode.MOCK_NOT_SUPPORTED,
            "get_sector_membership is only available with real market data",
            sector_name=sector_name,
        )

    try:
        membership = SERVICE.get_sector_membership(sector_name)
    except MarketError as exc:
        return error_payload(exc.error_code, exc.message, sector_name=sector_name)

    return {
        "success": True,
        "sector_name": sector_name,
        **membership.to_tool_dict(),
    }


@mcp.tool()
def get_market_breadth(date: str) -> dict[str, Any]:
    """
    获取指定交易日 A 股市场广度、涨跌停、连板、
    炸板以及昨日涨停股今日表现等市场情绪数据。

    用于判断市场赚钱/亏钱效应、接力生态、市场广度和市场阶段。

    仅返回结构化市场事实，不判断市场属于主升、轮动、亏钱效应或冰点。

    Args:
        date: 交易日期，格式 YYYY-MM-DD。

    返回字段：
        所有 *_count 字段为数量（家）。
        所有 *_pct / *_rate 字段为百分比，取值区间 [0, 100]。
        broken_limit_rate = broken_limit_count / (broken_limit_count + limit_up_count) * 100。
        previous_limit_up.positive_rate / promotion_rate 基于 sample_size 计算。
    """

    mode_error = config_mode_error(SETTINGS)
    if mode_error is not None:
        return mode_error

    if SETTINGS.data_mode == DATA_MODE_REAL:
        try:
            breadth = SERVICE.get_market_breadth(date)
        except MarketError as exc:
            return error_payload(exc.error_code, exc.message, date=date)
        return {
            "success": True,
            "date": date,
            **breadth.to_tool_dict()
        }

    if not isinstance(date, str) or not date:
        return {
            "success": False,
            "date": date,
            "error": "date must be a non-empty string"
        }

    market_data = load_market_data()

    if date not in market_data:
        return {
            "success": False,
            "date": date,
            "error": "market data not found"
        }

    breadth_data = market_data[date].get("market_breadth")
    if breadth_data is None:
        return {
            "success": False,
            "date": date,
            "error": "market breadth data not found"
        }

    breadth = breadth_data["breadth"]
    limit_state = breadth_data["limit_state"]
    previous_limit_up = breadth_data["previous_limit_up"]
    extreme_move = breadth_data["extreme_move"]

    broken_denominator = (
        limit_state["broken_limit_count"] + limit_state["limit_up_count"]
    )
    broken_limit_rate = (
        round(limit_state["broken_limit_count"] / broken_denominator * 100, 2)
        if broken_denominator
        else 0.0
    )

    sample_size = previous_limit_up["sample_size"]
    positive_rate = (
        round(previous_limit_up["positive_count"] / sample_size * 100, 2)
        if sample_size
        else 0.0
    )
    promotion_rate = (
        round(previous_limit_up["promoted_count"] / sample_size * 100, 2)
        if sample_size
        else 0.0
    )

    return {
        "success": True,
        "date": date,
        "breadth": {
            "rising_count": breadth["rising_count"],
            "falling_count": breadth["falling_count"],
            "flat_count": breadth["flat_count"]
        },
        "limit_state": {
            "limit_up_count": limit_state["limit_up_count"],
            "limit_down_count": limit_state["limit_down_count"],
            "first_limit_up_count": limit_state["first_limit_up_count"],
            "multi_limit_up_count": limit_state["multi_limit_up_count"],
            "max_limit_height": limit_state["max_limit_height"],
            "broken_limit_count": limit_state["broken_limit_count"],
            "broken_limit_rate": broken_limit_rate
        },
        "previous_limit_up": {
            "sample_size": sample_size,
            "average_change_pct": previous_limit_up["average_change_pct"],
            "median_change_pct": previous_limit_up["median_change_pct"],
            "positive_rate": positive_rate,
            "promotion_rate": promotion_rate
        },
        "extreme_move": {
            "large_rise_count": extreme_move["large_rise_count"],
            "large_fall_count": extreme_move["large_fall_count"]
        }
    }


@mcp.tool()
def get_market_metric_baseline(
    date: str,
    metric: str,
    window: int = 20
) -> dict[str, Any]:
    """
    获取指定交易日期某个市场广度指标的历史基线（atomic fact）。

    仅返回数值证据：current、avg、median、percentile，以及样本完整性
    （sample_count / window / complete / missing_dates）。不判断高低强弱，
    不做 regime 分类，不输出任何语义结论。

    baseline sample = requested date 之前最近 N 个已完成交易日
    （sample_date < requested date）；current 单独保存，不进入 baseline。
    percentile = 100 * count(sample_value <= current) / sample_count。

    Args:
        date: 交易日期，格式 YYYY-MM-DD。
        metric: 指标名，例如 limit_up_count / broken_limit_rate / promotion_rate。
        window: 基线窗口（交易日数量），正整数，默认 20。

    返回字段：
        baseline.current / avg / median / percentile 为数值（可为 null）。
        baseline.complete=false 时 avg/median/percentile 均为 null，
        表示历史样本不足（INSUFFICIENT_HISTORY），而不是缩短窗口的结果。
    """

    mode_error = config_mode_error(SETTINGS)
    if mode_error is not None:
        return mode_error

    if SETTINGS.data_mode != DATA_MODE_REAL:
        return error_payload(
            ErrorCode.MOCK_NOT_SUPPORTED,
            "get_market_metric_baseline is only available with real market data",
            date=date,
            metric=metric,
        )

    try:
        baseline = SERVICE.get_market_metric_baseline(date, metric, window)
    except MarketError as exc:
        return error_payload(
            exc.error_code, exc.message, date=date, metric=metric
        )

    return {
        "success": True,
        "date": date,
        "baseline": baseline.to_tool_dict()
    }


@mcp.tool()
def get_market_history_summary(date: str) -> dict[str, Any]:
    """
    获取指定交易日的市场历史量能基准和主要指数 5日/20日表现。

    用于判断当前市场相对前一交易日是否放量/缩量、
    当前成交额相对 5日/20日均值的位置，以及指数中短期趋势背景。

    仅返回结构化统计事实，不直接判断市场状态。

    市场总成交额口径为上证指数 + 深证成指成交额之和，
    不重复计入作为深市子集的创业板指成交额。

    Args:
        date: 交易日期，格式 YYYY-MM-DD。

    返回字段：
        所有 *_cny 字段为金额，单位人民币元。
        所有 *_pct 字段为百分比，取值可为负数。
    """

    mode_error = config_mode_error(SETTINGS)
    if mode_error is not None:
        return mode_error

    if SETTINGS.data_mode == DATA_MODE_MOCK:
        return _mock_market_history_summary(date)

    try:
        summary = SERVICE.get_market_history_summary(date)
    except MarketError as exc:
        return error_payload(exc.error_code, exc.message, date=date)

    return {
        "success": True,
        "date": date,
        **summary.to_tool_dict()
    }


def _mock_market_history_summary(date: str) -> dict[str, Any]:
    """Mock-mode implementation of get_market_history_summary."""

    if not isinstance(date, str) or not date:
        return {
            "success": False,
            "date": date,
            "error": "date must be a non-empty string"
        }

    market_data = load_market_data()

    if date not in market_data:
        return {
            "success": False,
            "date": date,
            "error": "market data not found"
        }

    if "market_history" not in market_data[date]:
        return {
            "success": False,
            "date": date,
            "error": "market history data not found"
        }

    indices = market_data[date].get("indices")
    if indices is None:
        return {
            "success": False,
            "date": date,
            "error": "index data not found"
        }

    history = market_data[date]["market_history"]
    turnover_history = history["turnover"]

    current_cny = sum(
        item["turnover"]
        for item in indices
        if item["code"] in TOTAL_TURNOVER_INDEX_CODES
    )

    previous_cny = turnover_history["previous_cny"]
    avg_5d_cny = turnover_history["avg_5d_cny"]
    avg_20d_cny = turnover_history["avg_20d_cny"]

    def change_pct(current: float, base: float) -> float | None:
        if not base:
            return None
        return round((current - base) / base * 100, 2)

    return {
        "success": True,
        "date": date,
        "turnover": {
            "current_cny": current_cny,
            "previous_cny": previous_cny,
            "avg_5d_cny": avg_5d_cny,
            "avg_20d_cny": avg_20d_cny,
            "vs_previous_pct": change_pct(current_cny, previous_cny),
            "vs_5d_pct": change_pct(current_cny, avg_5d_cny),
            "vs_20d_pct": change_pct(current_cny, avg_20d_cny)
        },
        "indices": [
            {
                "code": item["code"],
                "name": item["name"],
                "change_5d_pct": item["change_5d_pct"],
                "change_20d_pct": item["change_20d_pct"]
            }
            for item in history["indices"]
        ]
    }


@mcp.tool()
def get_sector_detail(date: str, sector_name: str) -> dict[str, Any]:
    """
    获取指定交易日期某个板块的详细表现，
    包括板块名称、涨跌幅、成交额和领涨个股列表。

    用于深入了解某个特定板块当日表现及其领涨个股。
    当已经从 get_sector_ranking 中获得板块名称、需要进一步下钻时调用。

    不用于获取板块之间的排名（请使用 get_sector_ranking），
    也不用于获取大盘指数行情（请使用 get_index_performance）。

    Args:
        date: 交易日期，格式 YYYY-MM-DD。
        sector_name: 板块名称，需与 get_sector_ranking 返回的名称一致。
    """

    mode_error = config_mode_error(SETTINGS)
    if mode_error is not None:
        return mode_error

    if SETTINGS.data_mode == DATA_MODE_REAL:
        try:
            ranking = []
            for kind in ("top", "bottom"):
                ranking.extend(SERVICE.get_sector_ranking(date, kind, 1000))
            snapshot = next((s for s in ranking if s.sector_name == sector_name), None)
            if snapshot is None:
                return error_payload(
                    ErrorCode.SECTOR_NOT_FOUND,
                    "sector %r not found in THS industry ranking" % sector_name,
                    date=date, sector_name=sector_name,
                )
            history = SERVICE.get_sector_history_summary(date, sector_name)
        except MarketError as exc:
            return error_payload(
                exc.error_code, exc.message, date=date, sector_name=sector_name
            )
        return {
            "success": True,
            "date": date,
            "sector_name": sector_name,
            "sector_id": snapshot.sector_id,
            "taxonomy": snapshot.taxonomy,
            "source_family": snapshot.source_family,
            "change_pct": snapshot.change_pct,
            "turnover": snapshot.turnover_cny,
            "turnover_cny": snapshot.turnover_cny,
            "up_count": snapshot.up_count,
            "down_count": snapshot.down_count,
            # Deliberately not provided: membership comes from a different
            # universe (Sina) and must not be mixed into THS sector facts.
            "leading_stocks": None,
            "history": history.to_tool_dict(),
        }

    market_data = load_market_data()

    if date not in market_data:
        return {
            "success": False,
            "date": date,
            "sector_name": sector_name,
            "error": "market data not found"
        }

    sectors = market_data[date].get("sectors")
    if sectors is None:
        return {
            "success": False,
            "date": date,
            "sector_name": sector_name,
            "error": "sector data not found"
        }

    for item in sectors:
        if item["sector_name"] == sector_name:
            return {
                "success": True,
                "date": date,
                "sector_name": item["sector_name"],
                "change_pct": item["change_pct"],
                "turnover": item["turnover"],
                "leading_stocks": item["leading_stocks"]
            }

    return {
        "success": False,
        "date": date,
        "sector_name": sector_name,
        "error": "sector not found"
    }


@mcp.tool()
def get_stock_detail(date: str, stock_code: str) -> dict[str, Any]:
    """
    获取指定交易日期某只 A 股个股的行情和交易数据，
    包括所属板块、前收盘、开盘、最高、最低、收盘、涨跌幅、
    成交量、成交额和换手率。

    用于分析个股当日价格表现、成交活跃度和日内走势。
    当已知股票代码、需要查看某只股票当日行情时调用。

    不提供新闻、上涨原因、投资建议或未来催化判断；
    不用于获取板块整体表现（请使用 get_sector_detail），
    也不用于获取大盘指数行情（请使用 get_index_performance）。

    Args:
        date: 交易日期，格式 YYYY-MM-DD。
        stock_code: 股票代码，需与行情数据中的代码一致，如 600519.SH。
    """

    mode_error = config_mode_error(SETTINGS)
    if mode_error is not None:
        return mode_error

    if SETTINGS.data_mode == DATA_MODE_MOCK:
        return _mock_stock_detail(date, stock_code)

    try:
        quote = SERVICE.get_stock_detail(date, stock_code)
    except MarketError as exc:
        return error_payload(exc.error_code, exc.message, date=date, stock_code=stock_code)

    return {
        "success": True,
        "date": date,
        "stock": quote.to_tool_dict()
    }


def _mock_stock_detail(date: str, stock_code: str) -> dict[str, Any]:
    """Mock-mode implementation of get_stock_detail."""

    if not isinstance(date, str) or not date:
        return {
            "success": False,
            "date": date,
            "stock_code": stock_code,
            "error": "date must be a non-empty string"
        }

    if not isinstance(stock_code, str) or not stock_code:
        return {
            "success": False,
            "date": date,
            "stock_code": stock_code,
            "error": "stock_code must be a non-empty string"
        }

    market_data = load_market_data()

    if date not in market_data:
        return {
            "success": False,
            "date": date,
            "stock_code": stock_code,
            "error": "market data not found"
        }

    stocks = market_data[date].get("stocks")
    if stocks is None:
        return {
            "success": False,
            "date": date,
            "stock_code": stock_code,
            "error": "stock data not found"
        }

    for item in stocks:
        if item["code"] == stock_code:
            return {
                "success": True,
                "date": date,
                "stock": {
                    "code": item["code"],
                    "name": item["name"],
                    "sector_name": item["sector_name"],
                    "previous_close": item["previous_close"],
                    "open": item["open"],
                    "high": item["high"],
                    "low": item["low"],
                    "close": item["close"],
                    "change_pct": item["change_pct"],
                    "volume": item["volume"],
                    "turnover": item["turnover"],
                    "turnover_rate": item["turnover_rate"]
                }
            }

    return {
        "success": False,
        "date": date,
        "stock_code": stock_code,
        "error": "stock not found"
    }


@mcp.tool()
def get_stock_news(date: str, stock_code: str, limit: int = 10) -> dict[str, Any]:
    """
    获取指定交易日期某只 A 股个股相关的重要新闻和公开事件，
    包括新闻编号、发布时间、来源、标题、摘要、事件类型和链接。

    当需要进一步分析某只股票当日上涨、下跌或异动的可能相关事件时调用，
    用于为个股当日异动提供 Evidence（证据）素材。

    只返回新闻和事件事实，不负责判断利好或利空、
    不判断新闻是否导致股价上涨或下跌、不判断哪个事件是主要涨跌原因、
    不预测未来股价、不提供投资建议、不生成未来催化结论。

    Args:
        date: 交易日期，格式 YYYY-MM-DD。
        stock_code: 股票代码，需与行情数据中的代码一致，如 688981.SH。
        limit: 返回的新闻数量上限，必须为正整数，默认 10。
    """

    mode_error = config_mode_error(SETTINGS)
    if mode_error is not None:
        return mode_error

    if SETTINGS.data_mode == DATA_MODE_REAL:
        try:
            items = SERVICE.get_stock_news(date, stock_code, limit)
        except MarketError as exc:
            return error_payload(
                exc.error_code, exc.message, date=date, stock_code=stock_code
            )
        return {
            "success": True,
            "date": date,
            "stock_code": stock_code,
            "count": len(items),
            "news": items,
            "evidence": {
                "date_semantics": "FILTERED_RECENT_WINDOW",
                "empty_semantics": "NO_ITEM_OBSERVED_IN_RETURNED_WINDOW",
                "causality": "NOT_ESTABLISHED",
            },
        }

    if not isinstance(date, str) or not date:
        return {
            "success": False,
            "date": date,
            "stock_code": stock_code,
            "error": "date must be a non-empty string"
        }

    if not isinstance(stock_code, str) or not stock_code:
        return {
            "success": False,
            "date": date,
            "stock_code": stock_code,
            "error": "stock_code must be a non-empty string"
        }

    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
        return {
            "success": False,
            "date": date,
            "stock_code": stock_code,
            "error": "limit must be a positive integer",
            "limit": limit
        }

    market_data = load_market_data()

    if date not in market_data:
        return {
            "success": False,
            "date": date,
            "stock_code": stock_code,
            "error": "market data not found"
        }

    stocks = market_data[date].get("stocks")
    if stocks is None:
        return {
            "success": False,
            "date": date,
            "stock_code": stock_code,
            "error": "stock data not found"
        }

    stock = next((item for item in stocks if item["code"] == stock_code), None)
    if stock is None:
        return {
            "success": False,
            "date": date,
            "stock_code": stock_code,
            "error": "stock not found"
        }

    news_map = market_data[date].get("news") or {}
    news_items = news_map.get(stock_code, [])

    selected = news_items[:limit]

    return {
        "success": True,
        "date": date,
        "stock": {
            "code": stock["code"],
            "name": stock["name"]
        },
        "count": len(selected),
        "news": [
            {
                "news_id": item["news_id"],
                "published_at": item["published_at"],
                "source": item["source"],
                "title": item["title"],
                "summary": item["summary"],
                "event_type": item["event_type"],
                "url": item["url"]
            }
            for item in selected
        ]
    }


# ============================================================
# Main
# ============================================================

if __name__ == "__main__":
    mcp.run()
