import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from collector.collector import collect, normalized_for
from collector.store import EvidenceStore
from collector.tests.test_evidence_store import DATE, FakeCaller, base_responses
from product.dashboard import render_dashboard
from product.pipeline import run_product_day
from review_memory.store import ReviewMemoryStore


def test_dashboard_fail_closed_history():
    review = {
        "date": DATE, "market": {"facts": [{"statement": "fact"}]},
        "market_regime": {"state": "UNCERTAIN", "confidence": "LOW"},
        "evidence_gaps": ["gap"], "tomorrow_watch_conditions": [],
    }
    outlook = {
        "patterns": [{
            "sector_name": "半导体",
            "current_state": {"sector_change_pct": 4.2},
            "statistics": {"t1": {
                "status": "INSUFFICIENT_SAMPLE", "sample_size": 2, "minimum_sample": 8
            }},
        }]
    }
    html = render_dashboard(review, outlook, {"status": "OPEN"})
    assert "历史样本不足" in html
    assert "Historical Pattern" in html


def test_one_command_replay_creates_memory_outlook_dashboard():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        data, out, failed, memory = (
            root / "data", root / "out", root / "failed", root / "memory"
        )
        responses = base_responses(broken20=False, promotion20=False)
        caller = FakeCaller(responses)
        collection = collect(caller, DATE)
        EvidenceStore(data).save(DATE, collection, normalized_for(collection))

        result = run_product_day(
            date=DATE, mode="replay", data_root=str(data), output_root=str(out),
            failed_root=str(failed), memory_root=str(memory),
            clock=lambda: "2026-10-01T00:00:00",
        )
        assert result["execution_status"] == "SUCCESS"
        day = out / DATE
        assert (day / "review.json").is_file()
        assert (day / "outlook.json").is_file()
        assert (day / "dashboard.html").is_file()
        assert (day / "product_manifest.json").is_file()
        assert ReviewMemoryStore(memory).exists(DATE)
        review = json.loads((day / "review.json").read_text(encoding="utf-8"))
        assert review["sectors"]["top_gainers"][0]["sector_name"] == "半导体"
        outlook = json.loads((day / "outlook.json").read_text(encoding="utf-8"))
        assert outlook["calibrated_pattern_count"] == 0


def test_settlement_can_use_market_days_without_memory_records():
    from product.pipeline import _settle_prior_records
    from review_memory.service import build_review_record

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        market_root, memory_root = root / "market", root / "memory"
        memory = ReviewMemoryStore(memory_root)

        base = {
            "date": "2026-09-01",
            "evidence": {},
            "sector_ranking": {"sectors": [
                {"sector_id": "881121", "sector_name": "半导体", "change_pct": 4.2}
            ]},
        }
        record = build_review_record(
            "2026-09-01",
            {"sectors": {}, "tomorrow_watch_conditions": [], "metric_claims": []},
            base,
        )
        memory.save("2026-09-01", record)

        for index in range(2, 7):
            date = "2026-09-0%d" % index
            day = market_root / date / "normalized"
            day.mkdir(parents=True)
            payload = {
                "date": date, "evidence": {},
                "sector_ranking": {"sectors": [
                    {"sector_id": "881121", "sector_name": "半导体", "change_pct": 1.0}
                ]},
            }
            (day / "market.json").write_text(json.dumps(payload), encoding="utf-8")

        _settle_prior_records(memory, market_root, "2026-09-06")
        assert memory.load("2026-09-01")["status"] == "SETTLED"
