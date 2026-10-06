"""Independent Eval tests for AGENT-F001 (offline, deterministic)."""

import sys
import unittest
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parent.parent
if str(EVAL_DIR) not in sys.path:
    sys.path.insert(0, str(EVAL_DIR))

from evaluator import evaluate_case, load_cases  # noqa: E402
from models import FAILURE_AGENT_F001, STATUS_FAIL, STATUS_PASS  # noqa: E402

CASES_PATH = EVAL_DIR / "cases" / "agent_f001.json"


class F001CasesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = {case.case_id: case for case in load_cases(str(CASES_PATH))}

    def _assert_expected(self, case_id):
        case = self.cases[case_id]
        result = evaluate_case(case)
        self.assertEqual(result.status, case.expected_result["status"])
        self.assertEqual(result.failure_codes, case.expected_result["failure_codes"])
        return result

    def test_001_confirmed_regime_with_incomplete_persistence_fails(self):
        result = self._assert_expected("AGENT-F001-001")
        self.assertEqual(result.status, STATUS_FAIL)
        self.assertIn(FAILURE_AGENT_F001, result.failure_codes)
        failing = [check for check in result.checks if check.passed is False]
        self.assertTrue(failing)
        self.assertEqual(failing[0].failure_code, FAILURE_AGENT_F001)
        self.assertEqual(failing[0].evidence_refs, ["E001"])
        self.assertEqual(failing[0].claim_refs, ["market_regime.state"])
        self.assertTrue(failing[0].reason)

    def test_002_uncertain_passes(self):
        result = self._assert_expected("AGENT-F001-002")
        self.assertEqual(result.status, STATUS_PASS)

    def test_003_complete_persistence_does_not_fire_f001(self):
        result = self._assert_expected("AGENT-F001-003")
        self.assertEqual(result.status, STATUS_PASS)

    def test_004_acknowledged_insufficiency_passes(self):
        result = self._assert_expected("AGENT-F001-004")
        self.assertEqual(result.status, STATUS_PASS)

    def test_deterministic_and_reproducible(self):
        for case in self.cases.values():
            self.assertEqual(evaluate_case(case), evaluate_case(case))


if __name__ == "__main__":
    unittest.main()
