#!/usr/bin/env python3
"""
MODULE 7 — Orchestrator / CLI. The last module — depends on 1 through 6
all existing. This is what ties everything together into the actual
"morning sequence" and is what a grader runs.

Planned commands:

    python3 agent/run_agent.py run
        For every referral in data/referral-queue.json, in order:
          1. log referral_read (Module 4)
          2. fetch resident history (Module 2) — catch failures; one
             referral's history fetch failing must not stop the run
             (policy 4.3 — the same "don't let one thing block the rest"
             principle applies to failures, not just escalations)
          3. classify it (Module 3)
          4. if autonomous: draft_triage_note (Module 6)
             if requires_approval: write_escalation (Module 6) and move on
             — no partial/preparatory version of the restricted action
          5. log the decision either way
        End with a summary: counts of autonomous / escalated / failed, and
        where the outputs and trace landed.

    python3 agent/run_agent.py list-pending
        Read output/escalations/*.json, filter to ones without a matching
        approval in approvals/approvals.json (Module 5), print them.

    python3 agent/run_agent.py approve <referral_id> --by "<name>" [--note "..."]
        Supervisor-only path. The only command allowed to call
        ApprovalGate.record_approval().

Should run with zero third-party dependencies (standard library only),
consistent with the rest of the data pack, and needs
services/history_service.py already running (see README.md).
"""

# TODO: build the argparse CLI and wire up Modules 1-6.
# Suggested paths (relative to this file's parent):
#   data/referral-queue.json
#   data/policy_rules.json          (via PolicyEngine)
#   approvals/approvals.json        (via ApprovalGate)
#   output/trace.jsonl              (via Trace)
#   output/triage_notes/
#   output/escalations/

if __name__ == "__main__":
    raise NotImplementedError("Module 7: build the CLI once Modules 1-6 are done.")
