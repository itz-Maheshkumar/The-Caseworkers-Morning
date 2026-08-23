"""
MODULE 8 — Tests / verification.

Not a formal requirement in the brief, but the fastest way to trust Module 3
before wiring the rest of the agent around it — and useful evidence for
DECISIONS.md ("how do you know the agent can't do X" is much stronger with
a test than with an assertion).

Suggested cases to cover once policy_engine.py exists, using referrals
straight out of data/referral-queue.json so the test doubles as a check
against the real data:

- A referral that should classify "autonomous" (e.g. a plain "Review
  award" or "Record change of address" request) — assert status and that
  matched_rules is empty.
- A referral whose requested_action is safe-sounding but whose summary
  isn't (the "reinstatement" one, RF-2026-0422 — requested_action literally
  says "Draft triage note for supervisor") — assert it still classifies
  "requires_approval". This is the one that catches a classifier that only
  looks at requested_action.
- A referral that obviously matches a restricted trigger (e.g. the
  Counter-Fraud "Suspend assistance" one) — assert "requires_approval" and
  check the right rule id shows up in matched_rules.
- Something that matches nothing recognisable at all — assert it defaults
  to "requires_approval" (policy 6.1), not "autonomous".

Once approval_gate.py (Module 5) exists, add a test that proves the
negative described there: calling apply_restricted_action() on an
unapproved referral_id raises ApprovalRequiredError.
"""

# TODO: write tests once policy_engine.py and approval_gate.py exist.
