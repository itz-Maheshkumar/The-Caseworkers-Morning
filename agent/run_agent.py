#!/usr/bin/env python3
"""
The Caseworker's Morning -- agent entrypoint. Wires Modules 1-6 together,
plus Amendment ACA-2026/2 (Modules 10-13).

    python3 agent/run_agent.py run
        Process every referral in data/referral-queue.json, in order: read
        it, pull the resident's history, classify it against the policy,
        and produce exactly one of three outcomes:
          - draft a triage note (autonomous, Section 2/2.4)
          - escalate it (Section 3.1-3.8 -- requires supervisor approval)
          - hand it off to a caseworker without drafting anything
            (Amendment ACA-2026/2, clause 3.9 -- household includes a
            minor, or composition couldn't be established at all)
        One referral escalating, failing to fetch, or requiring hand-off
        never stops the rest of the queue (policy 4.3).

    python3 agent/run_agent.py list-pending
        Show escalations awaiting supervisor approval.

    python3 agent/run_agent.py list-handoffs
        Show referrals handed off to a caseworker under clause 3.9. Not
        gated on approval -- a hand-off is ordinary casework a person must
        do, not a decision the Department must authorise (clause 3.3).

    python3 agent/run_agent.py approve RF-2026-XXXX --by "J. Wren" [--note "..."]
        Supervisor-only: record approval for one escalated referral. The
        only code path that writes to approvals/approvals.json. Applies to
        escalations only -- hand-offs have nothing to approve.

Requires services/history_service.py running first:
    python3 services/history_service.py --port 8083
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from policy_engine import PolicyEngine
from history_client import HistoryClient
from trace import Trace
from approval_gate import ApprovalGate
import triage

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
QUEUE_PATH = os.path.join(ROOT, "data", "referral-queue.json")
APPROVALS_PATH = os.path.join(ROOT, "approvals", "approvals.json")
TRACE_PATH = os.path.join(ROOT, "output", "trace.jsonl")
NOTES_DIR = os.path.join(ROOT, "output", "triage_notes")
ESCALATIONS_DIR = os.path.join(ROOT, "output", "escalations")
HANDOFFS_DIR = os.path.join(ROOT, "output", "handoffs")


def cmd_run(args):
    with open(QUEUE_PATH, encoding="utf-8") as f:
        referrals = json.load(f)

    engine = PolicyEngine()
    history = HistoryClient(base_url=args.history_url)

    autonomous, escalated, handed_off, fetch_failures = 0, 0, 0, 0

    with Trace(TRACE_PATH) as trace:
        trace.log("run_started", referral_count=len(referrals))

        for referral in referrals:
            rid = referral["referral_id"]
            trace.log("referral_read", referral_id=rid, resident_ref=referral["resident_ref"],
                       requested_action=referral["requested_action"])

            resident = history.get_resident(referral["resident_ref"])
            if "error" in resident:
                # A failed fetch no longer drops the referral outright --
                # classify() only needs the referral's own text, so
                # classification still proceeds below. What resident=None
                # actually changes is handled per-branch further down.
                trace.log("history_fetch_failed", referral_id=rid, reason=resident["error"])
                resident = None
                fetch_failures += 1
            else:
                trace.log("history_retrieved", referral_id=rid, resident_ref=referral["resident_ref"])

            decision = engine.classify(referral)
            rule_ids = [r["id"] for r in decision.matched_rules]
            trace.log("policy_decision", referral_id=rid, status=decision.status,
                       rule_ids=",".join(rule_ids) if rule_ids else "-", reason=decision.reason)

            if decision.status == "requires_approval":
                # No restricted action, and no partial/preparatory version
                # of it, is performed (policy 4.1) -- the only thing this
                # branch does is describe the situation for a supervisor.
                # Unaffected by clause 3.9: an escalation already means no
                # note gets drafted, which is all 3.9 actually requires.
                path = triage.write_escalation(referral, resident, decision, ESCALATIONS_DIR)
                trace.log("escalated", referral_id=rid, rule_ids=",".join(rule_ids),
                           path=os.path.relpath(path, ROOT))
                escalated += 1
                continue

            # decision.status == "autonomous" from here. Amendment
            # ACA-2026/2 clause 3.9: check household composition BEFORE
            # drafting anything -- 2.2 prohibits producing the draft
            # itself, not merely its adoption, so this check has to gate
            # draft_triage_note(), not run alongside it.
            household_decision = engine.check_household_restriction(resident)
            trace.log("household_checked", referral_id=rid, status=household_decision.status,
                       reason=household_decision.reason)

            if household_decision.status == "handoff_required":
                path = triage.write_handoff(referral, resident, household_decision, HANDOFFS_DIR)
                trace.log("handed_off", referral_id=rid, path=os.path.relpath(path, ROOT))
                handed_off += 1
            else:
                path = triage.draft_triage_note(referral, resident, NOTES_DIR)
                trace.log("triage_note_drafted", referral_id=rid, path=os.path.relpath(path, ROOT))
                autonomous += 1

        trace.log("run_finished", autonomous=autonomous, escalated=escalated,
                   handed_off=handed_off, fetch_failures=fetch_failures)

    print()
    print(f"Done. {autonomous} drafted autonomously, {escalated} escalated for "
          f"supervisor approval, {handed_off} handed off to a caseworker "
          f"(amendment ACA-2026/2).")
    if fetch_failures:
        print(f"({fetch_failures} history fetch(es) failed -- handled via escalation "
              f"or hand-off above, not dropped.)")
    print(f"Trace:       {os.path.relpath(TRACE_PATH, ROOT)}")
    print(f"Notes:       {os.path.relpath(NOTES_DIR, ROOT)}/")
    print(f"Escalations: {os.path.relpath(ESCALATIONS_DIR, ROOT)}/")
    print(f"Hand-offs:   {os.path.relpath(HANDOFFS_DIR, ROOT)}/")


def cmd_list_pending(args):
    gate = ApprovalGate(APPROVALS_PATH)
    escalation_files = [f for f in os.listdir(ESCALATIONS_DIR) if f.endswith(".json")] \
        if os.path.isdir(ESCALATIONS_DIR) else []
    if not escalation_files:
        print("No escalations yet -- run `run` first.")
        return

    pending = []
    for fname in sorted(escalation_files):
        with open(os.path.join(ESCALATIONS_DIR, fname), encoding="utf-8") as f:
            rec = json.load(f)
        if not gate.is_approved(rec["referral_id"]):
            pending.append(rec)

    if not pending:
        print("No escalations awaiting approval.")
        return

    for rec in pending:
        rule_ids = ", ".join(r["id"] for r in rec["matched_rules"])
        print(f"- {rec['referral_id']}  [{rule_ids}]  {rec['requested_action']!r}")
        print(f"    resident={rec['resident_ref']}  reason={rec['reason']}")


def cmd_approve(args):
    gate = ApprovalGate(APPROVALS_PATH)
    path = os.path.join(ESCALATIONS_DIR, f"{args.referral_id}.json")
    if not os.path.exists(path):
        print(f"No escalation found for {args.referral_id}. Run `list-pending` to see what's outstanding.")
        sys.exit(1)

    gate.record_approval(args.referral_id, approved_by=args.by, note=args.note or "")

    with open(path, encoding="utf-8") as f:
        rec = json.load(f)
    rule_ids = [r["id"] for r in rec["matched_rules"]]
    result = gate.apply_restricted_action(args.referral_id, rule_ids=rule_ids)

    print(f"Approved {args.referral_id} by {args.by}.")
    print(json.dumps(result, indent=2))


def cmd_list_handoffs(args):
    """
    List referrals handed off under clause 3.9. Deliberately not folded
    into cmd_list_pending() or filtered by ApprovalGate: a hand-off has
    nothing awaiting approval (clause 3.3 -- it isn't an escalation), so
    "pending" doesn't apply to it. Kept as a separate command for the same
    reason write_handoff() writes to a separate directory: distinguishability.
    """
    handoff_files = [f for f in os.listdir(HANDOFFS_DIR) if f.endswith(".json")] \
        if os.path.isdir(HANDOFFS_DIR) else []
    if not handoff_files:
        print("No hand-offs yet -- run `run` first.")
        return

    for fname in sorted(handoff_files):
        with open(os.path.join(HANDOFFS_DIR, fname), encoding="utf-8") as f:
            rec = json.load(f)
        rule_ids = ", ".join(r["id"] for r in rec["matched_rules"])
        print(f"- {rec['referral_id']}  [{rule_ids}]  {rec['requested_action']!r}")
        print(f"    resident={rec['resident_ref']}  reason={rec['reason']}")


def main():
    ap = argparse.ArgumentParser(description="The Caseworker's Morning agent")
    ap.add_argument("--history-url", default="http://127.0.0.1:8083")
    sub = ap.add_subparsers(dest="command", required=True)

    sub.add_parser("run", help="Process the referral queue")
    sub.add_parser("list-pending", help="List escalations awaiting approval")
    sub.add_parser("list-handoffs", help="List referrals handed off to a caseworker (amendment ACA-2026/2)")

    p_approve = sub.add_parser("approve", help="Supervisor: approve one escalated referral")
    p_approve.add_argument("referral_id")
    p_approve.add_argument("--by", required=True, help="Approving supervisor's name")
    p_approve.add_argument("--note", default="")

    args = ap.parse_args()
    {
        "run": cmd_run,
        "list-pending": cmd_list_pending,
        "list-handoffs": cmd_list_handoffs,
        "approve": cmd_approve,
    }[args.command](args)


if __name__ == "__main__":
    main()
