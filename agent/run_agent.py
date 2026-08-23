#!/usr/bin/env python3
"""
The Caseworker's Morning -- agent entrypoint. Wires Modules 1-6 together.

    python3 agent/run_agent.py run
        Process every referral in data/referral-queue.json, in order: read
        it, pull the resident's history, classify it against the policy,
        and either draft a triage note (autonomous) or escalate it
        (requires approval). One referral's history fetch failing, or one
        referral escalating, never stops the rest of the queue (policy 4.3).

    python3 agent/run_agent.py list-pending
        Show escalations awaiting supervisor approval.

    python3 agent/run_agent.py approve RF-2026-XXXX --by "J. Wren" [--note "..."]
        Supervisor-only: record approval for one escalated referral. The
        only code path that writes to approvals/approvals.json.

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


def cmd_run(args):
    with open(QUEUE_PATH, encoding="utf-8") as f:
        referrals = json.load(f)

    engine = PolicyEngine()
    history = HistoryClient(base_url=args.history_url)

    autonomous, escalated, failed = 0, 0, 0

    with Trace(TRACE_PATH) as trace:
        trace.log("run_started", referral_count=len(referrals))

        for referral in referrals:
            rid = referral["referral_id"]
            trace.log("referral_read", referral_id=rid, resident_ref=referral["resident_ref"],
                       requested_action=referral["requested_action"])

            resident = history.get_resident(referral["resident_ref"])
            if "error" in resident:
                # One referral's history not being fetchable must not lose
                # the work already done on the others (policy 4.3's
                # "escalating one doesn't stop the rest" applies equally
                # to failures, not just escalations).
                trace.log("history_fetch_failed", referral_id=rid, reason=resident["error"])
                failed += 1
                continue

            trace.log("history_retrieved", referral_id=rid, resident_ref=referral["resident_ref"])

            decision = engine.classify(referral)
            rule_ids = [r["id"] for r in decision.matched_rules]
            trace.log("policy_decision", referral_id=rid, status=decision.status,
                       rule_ids=",".join(rule_ids) if rule_ids else "-", reason=decision.reason)

            if decision.status == "autonomous":
                path = triage.draft_triage_note(referral, resident, NOTES_DIR)
                trace.log("triage_note_drafted", referral_id=rid, path=os.path.relpath(path, ROOT))
                autonomous += 1
            else:
                # No restricted action, and no partial/preparatory version
                # of it, is performed (policy 4.1) -- the only thing this
                # branch does is describe the situation for a supervisor.
                path = triage.write_escalation(referral, resident, decision, ESCALATIONS_DIR)
                trace.log("escalated", referral_id=rid, rule_ids=",".join(rule_ids),
                           path=os.path.relpath(path, ROOT))
                escalated += 1

        trace.log("run_finished", autonomous=autonomous, escalated=escalated, failed=failed)

    print()
    print(f"Done. {autonomous} drafted autonomously, {escalated} escalated for "
          f"supervisor approval, {failed} could not be retrieved.")
    print(f"Trace:       {os.path.relpath(TRACE_PATH, ROOT)}")
    print(f"Notes:       {os.path.relpath(NOTES_DIR, ROOT)}/")
    print(f"Escalations: {os.path.relpath(ESCALATIONS_DIR, ROOT)}/")


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


def main():
    ap = argparse.ArgumentParser(description="The Caseworker's Morning agent")
    ap.add_argument("--history-url", default="http://127.0.0.1:8083")
    sub = ap.add_subparsers(dest="command", required=True)

    sub.add_parser("run", help="Process the referral queue")
    sub.add_parser("list-pending", help="List escalations awaiting approval")

    p_approve = sub.add_parser("approve", help="Supervisor: approve one escalated referral")
    p_approve.add_argument("referral_id")
    p_approve.add_argument("--by", required=True, help="Approving supervisor's name")
    p_approve.add_argument("--note", default="")

    args = ap.parse_args()
    {"run": cmd_run, "list-pending": cmd_list_pending, "approve": cmd_approve}[args.command](args)


if __name__ == "__main__":
    main()
