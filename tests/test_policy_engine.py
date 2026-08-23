"""
Tests for the policy engine (Module 3) and the approval gate (Module 5).

Standard library only (unittest), consistent with the rest of the project
-- nothing here needs a venv or pip install. Run with:

    python3 -m unittest discover -s tests -v

or directly:

    python3 tests/test_policy_engine.py
"""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "agent"))

from policy_engine import PolicyEngine  # noqa: E402
from approval_gate import ApprovalGate, ApprovalRequiredError  # noqa: E402

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")


class TestPolicyEngineClassification(unittest.TestCase):
    """Exercises policy_engine.py against the real policy_rules.json and
    the real referral queue -- not synthetic fixtures -- so a change to
    either data file is what these tests actually guard."""

    @classmethod
    def setUpClass(cls):
        cls.engine = PolicyEngine()
        with open(os.path.join(DATA_DIR, "referral-queue.json"), encoding="utf-8") as f:
            cls.referrals = json.load(f)
        cls.by_id = {r["referral_id"]: r for r in cls.referrals}

    def test_full_queue_splits_as_expected(self):
        """All 12 referrals classify correctly: exactly these 4 require
        approval, the other 8 are autonomous. This is the test that would
        catch a policy_rules.json edit accidentally widening or narrowing
        the restricted set."""
        expected_restricted = {"RF-2026-0415", "RF-2026-0419", "RF-2026-0422", "RF-2026-0423"}
        restricted = {r["referral_id"] for r in self.referrals
                      if self.engine.classify(r).status == "requires_approval"}
        self.assertEqual(restricted, expected_restricted)

    def test_routine_review_is_autonomous(self):
        d = self.engine.classify(self.by_id["RF-2026-0412"])
        self.assertEqual(d.status, "autonomous")
        self.assertEqual(d.matched_rules, [])

    def test_address_change_is_autonomous(self):
        d = self.engine.classify(self.by_id["RF-2026-0413"])
        self.assertEqual(d.status, "autonomous")

    def test_disguised_reinstatement_still_escalates(self):
        """RF-2026-0422's requested_action reads 'Draft triage note for
        supervisor' -- itself a permitted action -- but its summary
        describes an award reinstatement (policy 3.2). A classifier that
        only looked at requested_action would misclassify this one; this
        test is what would catch that regression."""
        d = self.engine.classify(self.by_id["RF-2026-0422"])
        self.assertEqual(d.status, "requires_approval")
        self.assertIn("3.2", [r["id"] for r in d.matched_rules])

    def test_suspend_request_matches_3_2(self):
        d = self.engine.classify(self.by_id["RF-2026-0415"])
        self.assertEqual(d.status, "requires_approval")
        self.assertEqual([r["id"] for r in d.matched_rules], ["3.2"])

    def test_payment_details_change_matches_3_4(self):
        d = self.engine.classify(self.by_id["RF-2026-0423"])
        self.assertEqual(d.status, "requires_approval")
        self.assertEqual([r["id"] for r in d.matched_rules], ["3.4"])

    def test_income_change_matches_3_1(self):
        d = self.engine.classify(self.by_id["RF-2026-0419"])
        self.assertEqual(d.status, "requires_approval")
        self.assertEqual([r["id"] for r in d.matched_rules], ["3.1"])

    def test_unrecognised_referral_fails_safe(self):
        """Policy 6.1: where it's unclear whether Section 3 applies, treat
        it as though it does. A referral matching no restricted trigger
        AND no recognised-safe pattern must default to requires_approval,
        not autonomous."""
        referral = {
            "referral_id": "TEST-UNKNOWN",
            "requested_action": "Do something entirely unanticipated",
            "summary": "This does not resemble anything in the trigger lists.",
        }
        d = self.engine.classify(referral)
        self.assertEqual(d.status, "requires_approval")
        self.assertEqual(d.matched_rules, [])

    def test_decision_to_dict_shape(self):
        """Module 6 (triage.py) and Module 7 (run_agent.py) both depend on
        this shape -- lock it in explicitly."""
        d = self.engine.classify(self.by_id["RF-2026-0415"])
        as_dict = d.to_dict()
        self.assertEqual(set(as_dict.keys()), {"status", "matched_rules", "reason"})
        for rule in as_dict["matched_rules"]:
            self.assertEqual(set(rule.keys()), {"id", "label", "description"})


class TestApprovalGate(unittest.TestCase):
    """Proves the hard gate holds -- the negative case matters more than
    the positive one here (see DECISIONS.md: 'what the agent is
    structurally incapable of doing, and how I know')."""

    def setUp(self):
        fd, self.tmp_path = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        os.remove(self.tmp_path)  # ApprovalGate creates it fresh
        self.gate = ApprovalGate(self.tmp_path)

    def tearDown(self):
        if os.path.exists(self.tmp_path):
            os.remove(self.tmp_path)

    def test_unapproved_referral_is_blocked(self):
        with self.assertRaises(ApprovalRequiredError):
            self.gate.apply_restricted_action("RF-2026-0415", rule_ids=["3.2"])

    def test_require_approval_raises_directly(self):
        with self.assertRaises(ApprovalRequiredError):
            self.gate.require_approval("RF-2026-0423")

    def test_approval_unblocks_only_that_referral(self):
        self.gate.record_approval("RF-2026-0415", approved_by="Test Supervisor")
        result = self.gate.apply_restricted_action("RF-2026-0415", rule_ids=["3.2"])
        self.assertEqual(result["referral_id"], "RF-2026-0415")

        # A different, unapproved referral must still be blocked -- the
        # gate is per-referral, not a global switch.
        with self.assertRaises(ApprovalRequiredError):
            self.gate.apply_restricted_action("RF-2026-0423", rule_ids=["3.4"])

    def test_duplicate_approval_does_not_duplicate_record(self):
        self.gate.record_approval("RF-2026-0415", approved_by="A")
        self.gate.record_approval("RF-2026-0415", approved_by="B")
        approvals = self.gate._load()
        count = sum(1 for a in approvals if a["referral_id"] == "RF-2026-0415")
        self.assertEqual(count, 1)

    def test_is_approved_reflects_store(self):
        self.assertFalse(self.gate.is_approved("RF-2026-0419"))
        self.gate.record_approval("RF-2026-0419", approved_by="Test Supervisor")
        self.assertTrue(self.gate.is_approved("RF-2026-0419"))


if __name__ == "__main__":
    unittest.main()
