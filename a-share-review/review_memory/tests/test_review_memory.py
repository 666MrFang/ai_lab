from review_memory.patterns import PatternEngine, compound_returns, state_signature
from review_memory.service import build_outlook, build_review_record, settle_record


def normalized(date, sector_change=4.5, market_change=1.0):
    return {
        "date": date,
        "evidence": {
            "index_quote:000001.SH:" + date: {
                "evidence_type": "index_quote",
                "index": "000001.SH",
                "change_pct": market_change,
            }
        },
        "sector_ranking": {
            "sectors": [
                {"sector_id": "881001", "sector_name": "半导体", "change_pct": sector_change},
                {"sector_id": "881002", "sector_name": "通信", "change_pct": 2.0},
            ]
        },
    }


def test_record_captures_decision_and_state():
    review = {
        "market_regime": {"state": "UNCERTAIN"},
        "sectors": {"main_theme_candidates": []},
        "tomorrow_watch_conditions": [{"target": "x"}],
        "metric_claims": [{"claim_id": "C001"}],
    }
    record = build_review_record("2026-10-01", review, normalized("2026-10-01"))
    assert record["status"] == "OPEN"
    assert record["pattern_states"][0]["sector_name"] == "半导体"
    assert record["review_snapshot"]["metric_claims"][0]["claim_id"] == "C001"


def test_settlement_uses_future_stored_snapshots():
    record = build_review_record(
        "2026-10-01",
        {"sectors": {}, "tomorrow_watch_conditions": [], "metric_claims": []},
        normalized("2026-10-01"),
    )
    future = [
        normalized("2026-10-02", 1.0),
        normalized("2026-10-03", -1.0),
        normalized("2026-10-04", 2.0),
        normalized("2026-10-05", 0.5),
        normalized("2026-10-06", 1.0),
    ]
    settled = settle_record(record, future)
    assert settled["status"] == "SETTLED"
    outcomes = settled["pattern_states"][0]["outcomes"]
    assert outcomes["t1_sector_return_pct"] == 1.0
    assert "t3_sector_return_pct" in outcomes
    assert "t5_sector_return_pct" in outcomes


def test_future_records_never_leak_into_pattern():
    current = {"market_change_pct": 1.0, "sector_change_pct": 4.2, "sector_rank": 1}
    past = {
        "date": "2026-09-01", "status": "SETTLED",
        "pattern_states": [{**current, "outcomes": {"t1_sector_return_pct": 2.0}}],
    }
    future = {
        "date": "2026-10-10", "status": "SETTLED",
        "pattern_states": [{**current, "outcomes": {"t1_sector_return_pct": -9.0}}],
    }
    result = PatternEngine(min_sample=1).match([past, future], "2026-10-06", current)
    assert result["sample_size"] == 1
    assert result["average_return_pct"] == 2.0


def test_small_sample_is_not_calibrated():
    current = {"market_change_pct": 1.0, "sector_change_pct": 4.2, "sector_rank": 1}
    result = PatternEngine(min_sample=8).match([], "2026-10-06", current)
    assert result["status"] == "INSUFFICIENT_SAMPLE"
    assert result["positive_rate"] is None


def test_calibrated_statistics():
    state = {"market_change_pct": 1.0, "sector_change_pct": 4.2, "sector_rank": 1}
    records = []
    for i, value in enumerate([1, 2, -1, 3]):
        records.append({
            "date": "2026-09-%02d" % (i + 1),
            "status": "SETTLED",
            "pattern_states": [{**state, "outcomes": {"t1_sector_return_pct": value}}],
        })
    result = PatternEngine(min_sample=4).match(records, "2026-10-06", state)
    assert result["status"] == "CALIBRATED"
    assert result["positive_rate"] == 75.0
    assert result["average_return_pct"] == 1.25


def test_signature_is_explicit_and_reproducible():
    assert state_signature({
        "market_change_pct": 0.9,
        "sector_change_pct": 4.35,
        "sector_rank": 1,
    }) == {
        "market_direction": "UP",
        "sector_move": "SURGE_4P",
        "sector_rank": "TOP1",
        "sector_5d": "UNKNOWN",
        "sector_volume": "UNKNOWN",
    }


def test_compound_return():
    assert compound_returns([10.0, -10.0]) == -1.0


def test_outlook_declares_non_prediction():
    current = build_review_record(
        "2026-10-06",
        {"sectors": {}, "tomorrow_watch_conditions": [], "metric_claims": []},
        normalized("2026-10-06"),
    )
    result = build_outlook("2026-10-06", current, [], min_sample=8)
    assert result["nature"] == "HISTORICAL_CALIBRATION_NOT_PREDICTION"
    assert result["calibrated_pattern_count"] == 0
    assert result["evidence_gaps"]


def test_sector_identity_prevents_cross_sector_outcome_leakage():
    current = {"market_change_pct": 1.0, "sector_change_pct": 4.2, "sector_rank": 1,
               "sector_id": "A", "sector_name": "半导体"}
    other = {"market_change_pct": 1.0, "sector_change_pct": 4.2, "sector_rank": 1,
             "sector_id": "B", "sector_name": "银行"}
    record = {
        "date": "2026-09-01", "status": "SETTLED",
        "pattern_states": [{**other, "outcomes": {"t1_sector_return_pct": -9.0}}],
    }
    result = PatternEngine(min_sample=1).match([record], "2026-10-06", current)
    assert result["sample_size"] == 0


def test_signature_uses_persistence_and_volume_when_complete():
    assert state_signature({
        "market_change_pct": 1.0,
        "sector_change_pct": 4.5,
        "sector_rank": 1,
        "sector_change_5d_pct": 8.0,
        "sector_history_5d_complete": True,
        "sector_turnover_vs_5d_pct": 35.0,
    }) == {
        "market_direction": "UP",
        "sector_move": "SURGE_4P",
        "sector_rank": "TOP1",
        "sector_5d": "UP_5P",
        "sector_volume": "EXPANDED_30P",
    }


def test_incomplete_persistence_is_unknown_not_inferred():
    signature = state_signature({
        "market_change_pct": 1.0, "sector_change_pct": 4.5, "sector_rank": 1,
        "sector_change_5d_pct": 8.0, "sector_history_5d_complete": False,
    })
    assert signature["sector_5d"] == "UNKNOWN"
