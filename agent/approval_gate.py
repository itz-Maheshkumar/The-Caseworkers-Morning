"""
MODULE 5 — Approval gate. This is the floor requirement that matters most:

    "A hard approval gate on irreversible actions. Hard means the action
    cannot proceed without approval — not that the agent is instructed to
    ask nicely. A guardrail that consists only of an instruction in a
    prompt is not a guardrail."

Two things have to both be true when this module is done:

1. There must be NO code path, anywhere in this repo, from a referral
   flagged requires_approval to an actual mutation — because
   history_client.py only ever calls GET endpoints, there shouldn't be a
   mutating function to call in the first place. That's the structural
   half of the guardrail and it comes largely for free from Module 2 being
   built correctly (keep it read-only).

2. This module is the explicit, demonstrable half: a function that stands
   in for "the point where a real system would act on an approved
   referral" (call it apply_restricted_action or similar) must refuse to
   run unless a human has already recorded approval for that referral —
   checked against a durable store (suggest approvals/approvals.json).
   The ONLY code that should ever write an approval record is a
   supervisor-facing command (see run_agent.py's `approve` subcommand,
   Module 7) — never the agent's own decision loop.

Contract:

    class ApprovalRequiredError(Exception): ...

    class ApprovalGate:
        def __init__(self, approvals_path): ...
        def is_approved(self, referral_id: str) -> bool: ...
        def record_approval(self, referral_id: str, approved_by: str, note: str = "") -> None: ...
        def require_approval(self, referral_id: str) -> None:
            # raises ApprovalRequiredError if not approved
        def apply_restricted_action(self, referral_id: str, rule_ids) -> dict:
            # calls require_approval() first; only returns if it doesn't raise

Test this module by proving the negative: call apply_restricted_action() on
an id with no approval record and confirm it raises. That's the artifact
worth keeping (a short script or a test in tests/) since DECISIONS.md will
need to point at how you verified the gate actually holds.
"""

# TODO: implement ApprovalRequiredError and ApprovalGate
