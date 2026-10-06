import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from providers.akshare_provider import AkShareProvider


class CninfoClient:
    def __init__(self):
        self.calls = []

    def stock_zh_a_disclosure_report_cninfo(
        self, symbol, market, keyword, category, start_date, end_date
    ):
        self.calls.append(("cninfo", symbol, start_date, end_date))
        return [{
            "代码": symbol, "简称": "中芯国际", "公告标题": "测试公告",
            "公告时间": "2026-10-06", "公告链接": "https://example/cninfo",
        }]

    def stock_individual_notice_report(self, **kwargs):
        raise AssertionError("CNINFO must be preferred")


class EastmoneyOnlyClient:
    def stock_individual_notice_report(
        self, security, symbol, begin_date, end_date
    ):
        assert security == "688981"
        assert symbol == "全部"
        assert begin_date == end_date == "20261006"
        return [{
            "代码": security, "名称": "中芯国际", "公告标题": "备用公告",
            "公告类型": "重大事项", "公告日期": "2026-10-06",
            "网址": "https://example/eastmoney",
        }]


def test_disclosure_prefers_cninfo_and_exact_date():
    p = AkShareProvider(client=CninfoClient())
    items = p.get_stock_disclosures("2026-10-06", "688981.SH", 10)
    assert len(items) == 1
    assert items[0]["title"] == "测试公告"
    assert items[0]["source"] == "巨潮资讯"
    assert items[0]["lineage"]["source"] == "cninfo"


def test_disclosure_falls_back_to_eastmoney_when_cninfo_endpoint_absent():
    p = AkShareProvider(client=EastmoneyOnlyClient())
    items = p.get_stock_disclosures("2026-10-06", "688981.SH", 10)
    assert len(items) == 1
    assert items[0]["category"] == "重大事项"
    assert items[0]["lineage"]["endpoint"] == "stock_individual_notice_report"
