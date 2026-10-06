import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from collector.collector import collect, normalized_for
from collector.tests.test_evidence_store import DATE, FakeCaller, base_responses, key
from review_memory.service import build_review_record
from review_memory.patterns import state_signature


def test_top_sector_history_flows_into_pattern_state():
    responses = base_responses(broken20=False, promotion20=False)
    responses[key("get_sector_history_summary", date=DATE, sector_name="半导体")] = {
        "success": True, "date": DATE, "sector_id": "881121",
        "sector_name": "半导体", "taxonomy": "industry", "source_family": "ths",
        "change_pct_5d": 8.2, "change_pct_20d": 15.0,
        "turnover_cny": 1.7e11, "turnover_avg_5d_cny": 1.2e11,
        "turnover_avg_20d_cny": 1.0e11,
        "history_5d_complete": True, "history_20d_complete": True,
        "sample_count_5d": 5, "sample_count_20d": 20,
    }
    collection = collect(FakeCaller(responses), DATE)
    normalized = normalized_for(collection)
    assert normalized["sector_history"]["881121"]["change_pct_5d"] == 8.2

    record = build_review_record(
        DATE, {"sectors": {}, "tomorrow_watch_conditions": [], "metric_claims": []},
        normalized,
    )
    state = record["pattern_states"][0]
    assert state["sector_change_5d_pct"] == 8.2
    assert state["sector_turnover_vs_5d_pct"] > 30
    signature = state_signature(state)
    assert signature["sector_5d"] == "UP_5P"
    assert signature["sector_volume"] == "EXPANDED_30P"
