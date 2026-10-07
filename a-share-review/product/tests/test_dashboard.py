from product.dashboard import render_dashboard


def test_dashboard_separates_market_news_and_disclosures():
    review = {
        "date": "2026-10-06",
        "market_regime": {"state": "UNCERTAIN", "confidence": "LOW"},
        "market": {"facts": [{"statement": "两市成交额 1000000000000 元。"}]},
        "sectors": {"top_gainers": [], "top_losers": []},
        "stocks": [{
            "name": "测试股", "code": "600000", "sector_name": "银行",
            "roles": ["CAPACITY_CORE_CANDIDATE"],
            "facts": [
                {"statement": "5日涨幅 2.0%。"},
                {"statement": "新闻 2026-10-06 [媒体] 新闻标题"},
                {"statement": "公司公告 2026-10-06 [巨潮资讯] 公告标题"},
            ],
        }],
        "tomorrow_watch_conditions": [], "evidence_gaps": [],
    }
    html = render_dashboard(review, {"patterns": []}, {"status": "OPEN"})
    assert "① 市场温度" in html
    assert "② 强弱行业" in html
    assert "③ 核心个股与事件" in html
    assert "<th>新闻</th><th>公司公告</th>" in html
    assert "新闻标题" in html and "公告标题" in html
    assert "④ 明日观察与验证" in html
    assert "⑤ Evidence Gap" in html


def test_dashboard_prefers_canonical_stock_market_facts_over_model_text():
    review = {
        "date": "2026-09-29",
        "market_regime": {"state": "UNCERTAIN", "confidence": "LOW"},
        "market": {"facts": []},
        "sectors": {"top_gainers": [], "top_losers": []},
        "stocks": [{
            "name": "深物业A", "code": "000011", "sector_name": "房地产",
            "roles": ["LIMIT_UP_CORE_CANDIDATE"],
            "facts": [{"statement": "错误模型事实：成交额1.47亿元。"}],
        }],
        "tomorrow_watch_conditions": [], "evidence_gaps": [],
    }
    normalized = {
        "date": "2026-09-29",
        "hot_stocks": [{
            "date": "2026-09-29", "stock_code": "000011",
            "change_pct": 9.973, "consecutive_limit_up": 2,
            "turnover_cny": 971000000, "turnover_rate_pct": 17.07,
            "total_market_cap_cny": 7295000000,
            "first_limit_time": "09:31:00", "broken_count": 0,
        }],
        "sector_memberships": {},
        "stock_history": {},
    }
    html = render_dashboard(
        review, {"patterns": []}, {"status": "OPEN"}, normalized
    )
    assert "9.973" in html
    assert "9.71亿" in html
    assert "错误模型事实" not in html


def test_dashboard_fills_sector_history_from_normalized_evidence():
    review = {
        "date": "2026-09-29",
        "market_regime": {"state": "UNCERTAIN", "confidence": "LOW"},
        "market": {"facts": []},
        "sectors": {
            "top_gainers": [{"sector_name": "元件", "change_pct": 4.42, "turnover_cny": 83223000000}],
            "top_losers": [],
        },
        "stocks": [], "tomorrow_watch_conditions": [], "evidence_gaps": [],
    }
    normalized = {
        "sector_history": {
            "元件": {"change_pct_5d": -5.71, "change_pct_20d": 14.68}
        }
    }
    html = render_dashboard(
        review, {"patterns": []}, {"status": "OPEN"}, normalized
    )
    assert "-5.71%" in html
    assert "14.68%" in html
