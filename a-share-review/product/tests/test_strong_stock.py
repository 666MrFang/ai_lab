import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from runner.agent import ReferenceAgent


def _input(histories):
    members = [
        {"stock_code": "A", "stock_name": "A", "change_pct": 1, "market_cap_cny": 1},
        {"stock_code": "B", "stock_name": "B", "change_pct": 2, "market_cap_cny": 1},
        {"stock_code": "C", "stock_name": "C", "change_pct": 3, "market_cap_cny": 1},
        {"stock_code": "D", "stock_name": "D", "change_pct": 4, "market_cap_cny": 1},
    ]
    return {
        "date": "2026-09-30", "manifest": {},
        "normalized": {
            "evidence": {},
            "sector_ranking": {"sectors": []},
            "sector_memberships": {
                "S": {"sector_name": "样本行业", "stocks": members}
            },
            "stock_history": histories,
            "stock_news": {},
        },
    }


def _hist(value, complete=True):
    return {"change_pct_5d": value, "history_5d_complete": complete}


def test_complete_membership_marks_true_5d_top3_not_current_top3():
    result = ReferenceAgent()(_input({
        "A": _hist(20), "B": _hist(10), "C": _hist(5), "D": _hist(-2),
    }))["review"]
    roles = {x["code"]: x["roles"] for x in result["stocks"]}
    assert "STRONG_STOCK" in roles["A"]
    assert "STRONG_STOCK" in roles["B"]
    assert "STRONG_STOCK" in roles["C"]
    assert "STRONG_STOCK" not in roles["D"]


def test_one_missing_member_blocks_sector_top3_claim():
    result = ReferenceAgent()(_input({
        "A": _hist(20), "B": _hist(10), "C": _hist(5), "D": _hist(None, False),
    }))["review"]
    assert all("STRONG_STOCK" not in x["roles"] for x in result["stocks"])


def test_5d_tie_break_is_stock_code_deterministic():
    result = ReferenceAgent()(_input({
        "A": _hist(10), "B": _hist(10), "C": _hist(10), "D": _hist(10),
    }))["review"]
    strong = {x["code"] for x in result["stocks"] if "STRONG_STOCK" in x["roles"]}
    assert strong == {"A", "B", "C"}
