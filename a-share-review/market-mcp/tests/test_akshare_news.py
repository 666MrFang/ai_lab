import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from providers.akshare_provider import AkShareProvider


class FakeClient:
    def stock_news_em(self, symbol):
        assert symbol == "688981"
        return [
            {"新闻标题": "A", "新闻内容": "a", "发布时间": "2026-10-06 14:05:00",
             "文章来源": "媒体A", "新闻链接": "https://example/a"},
            {"新闻标题": "B", "新闻内容": "b", "发布时间": "2026-10-05 20:00:00",
             "文章来源": "媒体B", "新闻链接": "https://example/b"},
        ]


def test_news_filters_requested_date_and_keeps_timestamp():
    provider = AkShareProvider(client=FakeClient())
    items = provider.get_stock_news("2026-10-06", "688981.SH", 10)
    assert len(items) == 1
    assert items[0]["published_at"] == "2026-10-06 14:05:00"
    assert items[0]["title"] == "A"
    assert items[0]["lineage"]["source"] == "eastmoney"


def test_news_empty_means_no_observed_item_not_zero_fact():
    provider = AkShareProvider(client=FakeClient())
    assert provider.get_stock_news("2026-10-04", "688981.SH", 10) == []
