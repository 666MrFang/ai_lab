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
