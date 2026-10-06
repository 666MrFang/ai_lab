"""Independent Eval tests for AGENT-F002 (offline, deterministic)."""

import sys
import unittest
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parent.parent
if str(EVAL_DIR) not in sys.path:
    sys.path.insert(0, str(EVAL_DIR))

from evaluator import evaluate_case, load_cases  # noqa: E402
from models import (  # noqa: E402
    FAILURE_AGENT_F002,
    NOT_OBSERVABLE_NO_STRUCTURED_CLAIMS,
    OUT_OF_SCOPE_FORWARD_CLAIM,
    STATUS_FAIL,
    STATUS_NOT_OBSERVABLE,
    STATUS_OUT_OF_SCOPE,
    STATUS_PASS,
)

CASES_PATH = EVAL_DIR / "cases" / "agent_f002.json"


class F002CasesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = {case.case_id: case for case in load_cases(str(CASES_PATH))}

    def _assert_expected(self, case_id):
        case = self.cases[case_id]
        result = evaluate_case(case)
        self.assertEqual(result.status, case.expected_result["status"])
        self.assertEqual(result.failure_codes, case.expected_result["failure_codes"])
        return result

    def test_004_numeric_fact_only_passes(self):
        result = self._assert_expected("AGENT-F002-004")
        self.assertEqual(result.status, STATUS_PASS)

    def test_005_semantic_high_without_baseline_fails(self):
        result = self._assert_expected("AGENT-F002-005")
        self.assertEqual(result.status, STATUS_FAIL)
        self.assertIn(FAILURE_AGENT_F002, result.failure_codes)

    def test_006_semantic_high_with_incomplete_baseline_fails(self):
        result = self._assert_expected("AGENT-F002-006")
        failing = [check for check in result.checks if check.passed is False]
        self.assertEqual(failing[0].evidence_refs, ["E001"])

    def test_007_semantic_high_calibrated_passes(self):
        result = self._assert_expected("AGENT-F002-007")
        self.assertEqual(result.status, STATUS_PASS)
        passing = [check for check in result.checks if check.passed is True]
        self.assertTrue(passing)

    def test_008_semantic_high_contradicting_calibration_fails(self):
        result = self._assert_expected("AGENT-F002-008")
        self.assertEqual(result.status, STATUS_FAIL)
        self.assertIn(FAILURE_AGENT_F002, result.failure_codes)

    def test_009_semantic_low_calibrated_passes(self):
        result = self._assert_expected("AGENT-F002-009")
        self.assertEqual(result.status, STATUS_PASS)

    def test_010_forward_claim_is_out_of_scope_not_pass(self):
        result = self._assert_expected("AGENT-F002-010")
        self.assertEqual(result.status, STATUS_OUT_OF_SCOPE)
        self.assertIn(OUT_OF_SCOPE_FORWARD_CLAIM, result.out_of_scope)
        # MUST NOT be recorded as a clean F002 pass.
        self.assertNotEqual(result.status, STATUS_PASS)

    def test_011_missing_structured_claims_is_not_observable(self):
        result = self._assert_expected("AGENT-F002-011")
        self.assertEqual(result.status, STATUS_NOT_OBSERVABLE)
        self.assertIn(NOT_OBSERVABLE_NO_STRUCTURED_CLAIMS, result.not_observable)
        # NOT_OBSERVABLE must never be reported as a clean PASS.
        self.assertNotEqual(result.status, STATUS_PASS)

    def test_012_claims_without_contract_is_not_observable(self):
        result = self._assert_expected("AGENT-F002-012")
        self.assertEqual(result.status, STATUS_NOT_OBSERVABLE)
        self.assertIn(NOT_OBSERVABLE_NO_STRUCTURED_CLAIMS, result.not_observable)

    def test_deterministic_and_reproducible(self):
        for case in self.cases.values():
            self.assertEqual(evaluate_case(case), evaluate_case(case))


if __name__ == "__main__":
    unittest.main()
