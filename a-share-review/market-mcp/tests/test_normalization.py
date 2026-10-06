"""Unit tests for normalization helpers."""

import math
import unittest

from normalize.codes import normalize_code, normalize_code_parts
from normalize.dates import (
    coerce_to_iso_date,
    from_provider_date,
    is_valid_iso_date,
    normalize_iso_date,
    to_provider_date,
)
from normalize.metrics import change_pct, mean, pct_change_over_closes
from normalize.series import as_of, latest_n, total_turnover_by_date
from normalize.units import (
    hands_to_shares,
    qian_yuan_to_cny,
    ratio_to_pct,
    to_float,
    wan_yuan_to_cny,
    yi_yuan_to_cny,
)


class UnitConversionTest(unittest.TestCase):
    def test_qian_yuan_to_cny(self):
        # 1. Tushare amount is 千元; domain turnover is CNY 元.
        self.assertEqual(qian_yuan_to_cny(1000), 1_000_000.0)
        self.assertEqual(qian_yuan_to_cny("3050000"), 3_050_000_000.0)

    def test_hands_to_shares(self):
        # 2. Tushare vol is 手; domain volume is 股.
        self.assertEqual(hands_to_shares(100), 10_000.0)
        self.assertEqual(hands_to_shares("22"), 2_200.0)

    def test_wan_yuan_to_cny(self):
        self.assertEqual(wan_yuan_to_cny(500000), 5_000_000_000.0)

    def test_yi_yuan_to_cny(self):
        # SSE stock_sse_deal_daily values are 亿元.
        self.assertEqual(yi_yuan_to_cny(6800.23), 680_023_000_000.0)
        self.assertIsNone(yi_yuan_to_cny(None))

    def test_ratio_to_pct(self):
        # Sina turnover is a decimal ratio; domain uses percent.
        self.assertEqual(ratio_to_pct(0.01), 1.0)
        self.assertAlmostEqual(ratio_to_pct("0.003066"), 0.3066)
        self.assertIsNone(ratio_to_pct(None))
        self.assertIsNone(ratio_to_pct(""))


class PercentageUnitTest(unittest.TestCase):
    def test_change_pct_is_percent(self):
        # 3. Percentages stay in percent (4.35 means 4.35%), never scaled.
        self.assertEqual(change_pct(104.35, 100.0), 4.35)
        self.assertEqual(change_pct(95.65, 100.0), -4.35)

    def test_pct_change_over_closes(self):
        self.assertEqual(pct_change_over_closes([100, 101, 102, 103, 104, 110], 5), 10.0)
        self.assertIsNone(pct_change_over_closes([100, 101], 5))

    def test_change_pct_zero_base_is_none(self):
        self.assertIsNone(change_pct(10, 0))


class MissingValueTest(unittest.TestCase):
    def test_to_float_missing_variants(self):
        # 4. Missing stays None and is never coerced to 0.
        self.assertIsNone(to_float(None))
        self.assertIsNone(to_float(""))
        self.assertIsNone(to_float("   "))
        self.assertIsNone(to_float("not-a-number"))
        self.assertIsNone(to_float(math.nan))
        self.assertEqual(to_float("2.35"), 2.35)
        self.assertEqual(to_float(0), 0.0)

    def test_conversions_keep_none(self):
        self.assertIsNone(qian_yuan_to_cny(None))
        self.assertIsNone(hands_to_shares(None))
        self.assertIsNone(wan_yuan_to_cny(None))

    def test_mean_ignores_missing(self):
        self.assertEqual(mean([1.0, None, 3.0]), 2.0)
        self.assertIsNone(mean([None, None]))
        self.assertIsNone(mean([]))


class DateNormalizationTest(unittest.TestCase):
    def test_iso_to_compact_roundtrip(self):
        # 5. YYYY-MM-DD <-> YYYYMMDD.
        self.assertEqual(to_provider_date("2026-10-08"), "20261008")
        self.assertEqual(from_provider_date("20261008"), "2026-10-08")
        self.assertEqual(from_provider_date(to_provider_date("2026-01-01")), "2026-01-01")

    def test_invalid_dates(self):
        self.assertFalse(is_valid_iso_date("20261008"))
        self.assertFalse(is_valid_iso_date("2026-13-01"))
        self.assertFalse(is_valid_iso_date("2026-02-30"))
        self.assertFalse(is_valid_iso_date(""))
        self.assertIsNone(from_provider_date("bad"))
        self.assertIsNone(from_provider_date("20261301"))
        with self.assertRaises(ValueError):
            normalize_iso_date("2026/10/08")

    def test_coerce_to_iso_date(self):
        import datetime

        self.assertEqual(coerce_to_iso_date(datetime.date(2026, 9, 30)), "2026-09-30")
        self.assertEqual(
            coerce_to_iso_date(datetime.datetime(2026, 9, 30, 15, 0)), "2026-09-30"
        )
        self.assertEqual(coerce_to_iso_date("2026-09-30"), "2026-09-30")
        self.assertEqual(coerce_to_iso_date("20260930"), "2026-09-30")
        self.assertIsNone(coerce_to_iso_date("20261301"))
        self.assertIsNone(coerce_to_iso_date("not-a-date"))
        self.assertIsNone(coerce_to_iso_date(None))


class StockCodeNormalizationTest(unittest.TestCase):
    def test_known_suffixes(self):
        # 6. Stock code normalization.
        self.assertEqual(normalize_code_parts("600519.SH"), ("600519", "SH"))
        self.assertEqual(normalize_code_parts("600519.sh"), ("600519", "SH"))
        self.assertEqual(normalize_code_parts("000001.SZ"), ("000001", "SZ"))
        self.assertEqual(normalize_code_parts("830799.BJ"), ("830799", "BJ"))
        self.assertEqual(normalize_code("600519.SH"), "600519.SH")

    def test_bare_symbol_has_no_exchange(self):
        self.assertEqual(normalize_code_parts("600519"), ("600519", None))
        self.assertEqual(normalize_code("600519"), "600519")

    def test_invalid_codes(self):
        with self.assertRaises(ValueError):
            normalize_code_parts("ABCDEF.SH")
        with self.assertRaises(ValueError):
            normalize_code_parts("60051.SH")
        with self.assertRaises(ValueError):
            normalize_code_parts("600519.XX")
        with self.assertRaises(ValueError):
            normalize_code_parts(None)


class SeriesWindowTest(unittest.TestCase):
    def test_as_of_excludes_future_rows(self):
        rows = [
            {"date": "2026-10-06", "v": 1},
            {"date": "2026-10-08", "v": 2},
            {"date": "2026-10-09", "v": 3},
        ]
        kept = as_of(rows, "2026-10-08")
        self.assertEqual([row["date"] for row in kept], ["2026-10-06", "2026-10-08"])

    def test_latest_n(self):
        rows = [{"date": f"2026-10-0{i}"} for i in range(1, 6)]
        self.assertEqual(
            [row["date"] for row in latest_n(rows, 2)],
            ["2026-10-04", "2026-10-05"],
        )

    def test_total_turnover_excludes_non_market_codes(self):
        # 7. Market total must not double count ChiNext (399006.SZ).
        series = {
            "000001.SH": [{"date": "2026-10-08", "turnover_cny": 1_000_000.0}],
            "399001.SZ": [{"date": "2026-10-08", "turnover_cny": 2_000_000.0}],
            "399006.SZ": [{"date": "2026-10-08", "turnover_cny": 999_000_000.0}],
        }
        totals = total_turnover_by_date(series, ("000001.SH", "399001.SZ"))
        self.assertEqual(totals["2026-10-08"], 3_000_000.0)

    def test_total_turnover_skips_incomplete_dates(self):
        series = {
            "000001.SH": [{"date": "2026-10-08", "turnover_cny": 1.0}],
            "399001.SZ": [{"date": "2026-10-08", "turnover_cny": None}],
        }
        totals = total_turnover_by_date(series, ("000001.SH", "399001.SZ"))
        self.assertEqual(totals, {})


if __name__ == "__main__":
    unittest.main()
