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
