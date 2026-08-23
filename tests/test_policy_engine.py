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
import triage  # noqa: E402

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
SERVICES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "services")


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


class TestHouseholdRestriction(unittest.TestCase):
    """Amendment ACA-2026/2, clause 3.9 -- tests policy_engine.py's
    check_household_restriction() against the real resident history data
    (services/_history_data.json), not synthetic fixtures. Loads that data
    directly rather than going through HistoryClient, so these tests don't
    need services/history_service.py running -- consistent with the rest
    of this suite exercising real data files without a live server."""

    # Computed by hand against REFERRAL_BATCH_DATE (2026-03-17) in dates.py:
    # these are the only three residents in the data pack with a household
    # member under 18 as of that date.
    KNOWN_HANDOFF_REFERRALS = {"RF-2026-0412", "RF-2026-0416", "RF-2026-0418"}

    @classmethod
    def setUpClass(cls):
        cls.engine = PolicyEngine()
        with open(os.path.join(DATA_DIR, "referral-queue.json"), encoding="utf-8") as f:
            cls.referrals = json.load(f)
        with open(os.path.join(SERVICES_DIR, "_history_data.json"), encoding="utf-8") as f:
            cls.residents = json.load(f)
        cls.by_id = {r["referral_id"]: r for r in cls.referrals}

    def _resident_for(self, referral_id):
        ref = self.by_id[referral_id]["resident_ref"]
        return self.residents[ref]

    def test_known_handoff_referrals_have_a_minor_in_household(self):
        for rid in self.KNOWN_HANDOFF_REFERRALS:
            resident = self._resident_for(rid)
            d = self.engine.check_household_restriction(resident)
            self.assertEqual(d.status, "handoff_required", msg=f"{rid} should require hand-off")
            self.assertEqual([r["id"] for r in d.matched_rules], ["3.9"])

    def test_household_without_a_minor_is_clear(self):
        """RF-2026-0413's household (Module 1 fixture, unaffected by the
        amendment) has no member under 18 -- 3.9 must not fire for it."""
        resident = self._resident_for("RF-2026-0413")
        d = self.engine.check_household_restriction(resident)
        self.assertEqual(d.status, "clear")
        self.assertEqual(d.matched_rules, [])

    def test_full_queue_household_restriction_matches_known_three(self):
        """Among the 8 referrals classify() already puts in "autonomous"
        (Module 3's own split, re-derived here rather than hard-coded, so
        this test breaks if either classify() or the household data
        changes under it), exactly the three known referrals require a
        hand-off under 3.9."""
        autonomous_ids = {r["referral_id"] for r in self.referrals
                           if self.engine.classify(r).status == "autonomous"}
        handoff_ids = {rid for rid in autonomous_ids
                       if self.engine.check_household_restriction(
                           self._resident_for(rid)).status == "handoff_required"}
        self.assertEqual(handoff_ids, self.KNOWN_HANDOFF_REFERRALS)

    def test_resident_none_fails_safe_to_handoff(self):
        """Clause 5.2: an unfetchable history is treated the same as 3.9
        applying, not the same as 3.9 not applying."""
        d = self.engine.check_household_restriction(None)
        self.assertEqual(d.status, "handoff_required")
        self.assertIn("could not be established", d.reason)

    def test_resident_missing_household_key_fails_safe(self):
        """A resident record that came back but happens to have no
        "household" key is exactly as unknown as no resident at all --
        must fail the same way, not be treated as an empty (=clear)
        household."""
        d = self.engine.check_household_restriction({"resident_ref": "R-99999"})
        self.assertEqual(d.status, "handoff_required")

    def test_empty_household_list_is_clear(self):
        """Distinguish "we don't know the household" (fails safe to
        hand-off) from "we know it, and it's empty" (no minors possible,
        so clear) -- these are different facts and should get different
        answers."""
        d = self.engine.check_household_restriction({"resident_ref": "R-99999", "household": []})
        self.assertEqual(d.status, "clear")


class TestHandoffRecordsDistinguishability(unittest.TestCase):
    """Amendment clause 3.3: a hand-off must be distinguishable from an
    escalation, not just a relabelled copy of one. These tests exercise
    triage.write_handoff() and triage.write_escalation() directly and
    check the two outputs never collide."""

    REFERRAL = {
        "referral_id": "TEST-0001",
        "resident_ref": "R-TEST",
        "received_at": "2026-03-17T09:00:00",
        "source": "Test Harness",
        "summary": "Synthetic referral for a distinguishability test.",
        "requested_action": "Review award",
        "urgency": "Standard",
    }
    RESIDENT = {
        "resident_ref": "R-TEST",
        "status": "Active",
        "benefit_code": "HSP-A",
        "district": "Test District",
        "award_monthly": 500.0,
        "household": [{"name": "Junior Test", "date_of_birth": "2020-01-01", "relationship": "Son/daughter"}],
        "events": [],
    }

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.handoffs_dir = os.path.join(self.tmp.name, "handoffs")
        self.escalations_dir = os.path.join(self.tmp.name, "escalations")

    def tearDown(self):
        self.tmp.cleanup()

    def test_handoff_record_shape(self):
        engine = PolicyEngine()
        decision = engine.check_household_restriction(self.RESIDENT)
        self.assertEqual(decision.status, "handoff_required")

        path = triage.write_handoff(self.REFERRAL, self.RESIDENT, decision, self.handoffs_dir)
        with open(path, encoding="utf-8") as f:
            record = json.load(f)

        self.assertEqual(record["record_type"], "hand_off")
        self.assertEqual(record["status"], "HANDED_OFF_TO_CASEWORKER")
        self.assertIn("3.9", [r["id"] for r in record["matched_rules"]])

    def test_handoff_and_escalation_never_share_record_type_or_status(self):
        """The two record types must be tell-apart-able by field value
        alone, not just by which directory they happened to land in."""
        engine = PolicyEngine()
        household_decision = engine.check_household_restriction(self.RESIDENT)
        handoff_path = triage.write_handoff(self.REFERRAL, self.RESIDENT, household_decision, self.handoffs_dir)

        classify_decision = engine.classify({**self.REFERRAL, "summary": "Suspend the award pending review."})
        self.assertEqual(classify_decision.status, "requires_approval")
        escalation_path = triage.write_escalation(self.REFERRAL, self.RESIDENT, classify_decision, self.escalations_dir)

        with open(handoff_path, encoding="utf-8") as f:
            handoff = json.load(f)
        with open(escalation_path, encoding="utf-8") as f:
            escalation = json.load(f)

        self.assertNotEqual(handoff["record_type"], escalation["record_type"])
        self.assertNotEqual(handoff["status"], escalation["status"])
        # And they must not have landed in the same place either --
        # belt-and-braces on top of the field-level distinction.
        self.assertNotEqual(os.path.dirname(handoff_path), os.path.dirname(escalation_path))

    def test_handoff_never_mentions_note_being_drafted(self):
        """The agent_action_taken field is meant for a human reading the
        record without other context -- it must say plainly that nothing
        was drafted, not just that nothing was "adopted"."""
        engine = PolicyEngine()
        decision = engine.check_household_restriction(self.RESIDENT)
        path = triage.write_handoff(self.REFERRAL, self.RESIDENT, decision, self.handoffs_dir)
        with open(path, encoding="utf-8") as f:
            record = json.load(f)
        self.assertIn("No triage note was drafted", record["agent_action_taken"])


class TestAmendmentIntegration(unittest.TestCase):
    """Runs the real per-referral branch logic (classify -> household
    check -> draft/handoff) against the real queue and real resident data
    for the three known-affected referrals, without needing
    history_service.py running -- proving end to end that no triage note
    is ever produced for them, matching the live `run` test performed
    manually for Module 13."""

    KNOWN_HANDOFF_REFERRALS = {"RF-2026-0412", "RF-2026-0416", "RF-2026-0418"}

    @classmethod
    def setUpClass(cls):
        cls.engine = PolicyEngine()
        with open(os.path.join(DATA_DIR, "referral-queue.json"), encoding="utf-8") as f:
            cls.referrals = json.load(f)
        with open(os.path.join(SERVICES_DIR, "_history_data.json"), encoding="utf-8") as f:
            cls.residents = json.load(f)
        cls.by_id = {r["referral_id"]: r for r in cls.referrals}

    def test_no_triage_note_file_for_known_handoff_referrals(self):
        with tempfile.TemporaryDirectory() as tmp:
            notes_dir = os.path.join(tmp, "triage_notes")
            handoffs_dir = os.path.join(tmp, "handoffs")

            for rid in self.KNOWN_HANDOFF_REFERRALS:
                referral = self.by_id[rid]
                resident = self.residents[referral["resident_ref"]]

                decision = self.engine.classify(referral)
                self.assertEqual(decision.status, "autonomous",
                                  msg=f"{rid} is expected to be autonomous before the household check")

                household_decision = self.engine.check_household_restriction(resident)
                self.assertEqual(household_decision.status, "handoff_required")
                triage.write_handoff(referral, resident, household_decision, handoffs_dir)
                # Deliberately do NOT call draft_triage_note() here -- this
                # mirrors run_agent.cmd_run()'s branch, which gates on
                # household_decision.status before ever reaching it.

            note_files = os.listdir(notes_dir) if os.path.isdir(notes_dir) else []
            handoff_files = os.listdir(handoffs_dir) if os.path.isdir(handoffs_dir) else []
            self.assertEqual(note_files, [], msg="No triage note should exist for any hand-off referral")
            self.assertEqual(len(handoff_files), len(self.KNOWN_HANDOFF_REFERRALS))


if __name__ == "__main__":
    unittest.main()
