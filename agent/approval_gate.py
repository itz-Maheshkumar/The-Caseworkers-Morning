"""
The hard approval gate.

"Hard" means: there is no code path from a restricted referral to a
mutating action that does not pass through require_approval(), and
require_approval() raises unless a human has already written a matching
record into approvals/approvals.json *before* this run started.

This is deliberately NOT "the agent is instructed not to do it." Note what
already backs this up before this module even exists: agent/history_client.py
(Module 2) only calls GET endpoints against services/history_service.py,
which itself only implements do_GET -- there is no function anywhere in
this codebase that mutates a resident's award, payment, or eligibility.
apply_restricted_action() below is a stand-in for where such a mutation
would eventually be triggered in a real system (e.g. handing a case to the
payments system once a supervisor has cleared it); it exists only to prove
the gate holds even if something tried to call it.
"""
import json
import os
from datetime import datetime, timezone


class ApprovalRequiredError(Exception):
    pass


class ApprovalGate:
    def __init__(self, approvals_path):
        self.approvals_path = approvals_path
        os.makedirs(os.path.dirname(approvals_path), exist_ok=True)
        if not os.path.exists(approvals_path):
            with open(approvals_path, "w", encoding="utf-8") as f:
                json.dump([], f)

    def _load(self):
        with open(self.approvals_path, encoding="utf-8") as f:
            return json.load(f)

    def is_approved(self, referral_id):
        return any(a["referral_id"] == referral_id for a in self._load())

    def record_approval(self, referral_id, approved_by, note=""):
        """
        The ONLY function in this codebase that writes to approvals.json.
        Called only from run_agent.py's `approve` CLI subcommand -- a
        human explicitly running a command -- never from the agent's own
        run loop (cmd_run). If you grep this repo for calls to
        record_approval() and find one outside the CLI's `approve` path,
        that's a bug in the gate, not a feature.
        """
        approvals = self._load()
        if any(a["referral_id"] == referral_id for a in approvals):
            return  # already approved; don't duplicate the record
        approvals.append({
            "referral_id": referral_id,
            "approved_by": approved_by,
            "approved_at": datetime.now(timezone.utc).isoformat(),
            "note": note,
        })
        with open(self.approvals_path, "w", encoding="utf-8") as f:
            json.dump(approvals, f, indent=2)

    def require_approval(self, referral_id):
        """Raises unless a human already recorded approval for this exact
        referral_id. This is the check every gated action must call first."""
        if not self.is_approved(referral_id):
            raise ApprovalRequiredError(
                f"Referral {referral_id} requires supervisor approval before "
                f"any further action can proceed. No approval is recorded in "
                f"{self.approvals_path}."
            )

    def apply_restricted_action(self, referral_id, rule_ids=None):
        """
        Stand-in for the point where a real deployment would hand a
        cleared referral off to the system that actually performs the
        Section 3 action (award/payment/eligibility change). This agent
        never calls this from its own decision loop -- only a supervisor
        clearing the escalation queue triggers the equivalent step in a
        real system. Included so the gate is demonstrable, not just
        asserted: calling this without a prior approval always raises,
        and it performs no mutation itself even when it succeeds.
        """
        self.require_approval(referral_id)
        return {
            "referral_id": referral_id,
            "rule_ids": rule_ids,
            "cleared_at": datetime.now(timezone.utc).isoformat(),
            "note": "Approval confirmed. Handoff to the human-owned system of "
                    "record is now permitted; this agent still performs no "
                    "mutation itself -- see history_client.py (GET-only).",
        }
