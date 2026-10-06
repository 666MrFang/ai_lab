import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from collector.collector import collect, normalized_for
from collector.tests.test_evidence_store import DATE, FakeCaller, base_responses, key
from runner.agent import ReferenceAgent


def responses_with_verified_membership():
    responses = base_responses(broken20=False, promotion20=False)
    # Top sector has no verified mapping: explicit optional gap.
    responses[key("get_sector_membership", sector_name="半导体")] = {
        "success": False, "error_code": "SECTOR_MEMBERSHIP_UNAVAILABLE"
    }
    # Second sector has the repository's VERIFIED THS->Sina mapping.
    responses[key("get_sector_membership", sector_name="房地产")] = {
        "success": True,
        "sector_id": "881153", "sector_name": "房地产", "taxonomy": "industry",
        "source_family": "sina", "membership_semantics": "CURRENT_MEMBERSHIP_ONLY",
        "count": 2,
        "stocks": [
            {"stock_code": "600663", "stock_name": "陆家嘴", "change_pct": 3.2,
             "turnover_cny": 1.2e9, "turnover_rate_pct": 2.1,
             "market_cap_cny": 80_000_000_000},
            {"stock_code": "000001", "stock_name": "样本股", "change_pct": 5.0,
             "turnover_cny": 2.0e8, "turnover_rate_pct": 4.0,
             "market_cap_cny": 10_000_000_000},
        ],
    }
    return responses


def test_collector_persists_verified_membership_without_mixing_families():
    collection = collect(FakeCaller(responses_with_verified_membership()), DATE)
    normalized = normalized_for(collection)
    membership = normalized["sector_memberships"]["881153"]
    assert membership["source_family"] == "sina"
    assert membership["membership_semantics"] == "CURRENT_MEMBERSHIP_ONLY"
    assert normalized["sector_ranking"]["source_family"] == "ths"


def test_agent_marks_capacity_candidate_but_not_strong_stock():
    collection = collect(FakeCaller(responses_with_verified_membership()), DATE)
    normalized = normalized_for(collection)
    result = ReferenceAgent()({
        "date": DATE,
        "manifest": {
            "incomplete_evidence": collection.incomplete_evidence,
            "missing_capabilities": collection.missing_capabilities,
        },
        "normalized": normalized,
    })["review"]
    stock = next(x for x in result["stocks"] if x["code"] == "600663")
    assert "CAPACITY_CORE_CANDIDATE" in stock["roles"]
    assert "STRONG_STOCK" not in stock["roles"]
    assert any("5d" in gap for gap in stock["evidence_gaps"])


def test_current_top_mover_is_observation_not_leader():
    collection = collect(FakeCaller(responses_with_verified_membership()), DATE)
    normalized = normalized_for(collection)
    result = ReferenceAgent()({
        "date": DATE, "manifest": {}, "normalized": normalized
    })["review"]
    stock = next(x for x in result["stocks"] if x["code"] == "000001")
    assert stock["roles"] == ["OTHER"]
    assert stock["possible_drivers"] == []
