# Verification runbook

A step-by-step path through every function in this project — success case
and edge case — plus the CLI-level flow a demo or a grader would actually
run. Every command below was run against this exact codebase before being
written down here; expected output is real output, not a guess.

Two ways to use this: run `python3 -m unittest discover -s tests -v` for
the fast, automated version of almost everything in Part 2 (24 tests,
runs in well under a second, no mock service needed) — or walk through
this file by hand if you want to see each function's actual output for
yourself, or you're verifying behaviour the automated suite doesn't cover
(mainly the CLI-level commands in Part 3, which drive real subprocess
output rather than in-process return values).

## 0. One-time setup

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

Nothing to `pip install` — standard library only.

## 1. Fast path: the automated suite

```bash
python3 -m unittest discover -s tests -v
```

Expect `Ran 24 tests ... OK`. This alone covers: every classification
case in Part 2.2, every household-restriction case in Part 2.3, the
hand-off/escalation distinguishability checks in Part 2.5, and an
integration check that no triage note is ever produced for a hand-off
referral. It does **not** cover the approval gate (Part 2.4) or any CLI
command (Part 3) — those go through real files and a real subprocess, so
they're checked manually below instead.

## 2. Function-by-function: success and edge cases

Start the mock service first — everything from here on assumes it's
running:

```bash
python3 services/history_service.py --port 8083
```

### 2.1 `agent/history_client.py` — `HistoryClient`

```python
import sys; sys.path.insert(0, "agent")
from history_client import HistoryClient
hc = HistoryClient(base_url="http://127.0.0.1:8083")

hc.get_resident("R-20500")           # success
hc.get_resident("NOT-A-REAL-ID")     # edge: unknown resident
HistoryClient(base_url="http://127.0.0.1:9").get_resident("R-20500")  # edge: service unreachable
```

| Case | Result |
|---|---|
| Known resident | Full record: `status`, `benefit_code`, `district`, `award_monthly`, `household`, `events`. |
| Unknown resident ref | `{'error': 'not_found', 'resident_ref': 'NOT-A-REAL-ID'}` — a dict, not a raised exception, so callers never need a `try/except` just to check. |
| Service not running / wrong port | `{'error': 'unreachable', 'detail': '[Errno 111] Connection refused'}` — same shape as `not_found`, so every caller checks one thing: `"error" in result`. |

### 2.2 `agent/policy_engine.py` — `PolicyEngine.classify()`

```python
import json, sys; sys.path.insert(0, "agent")
from policy_engine import PolicyEngine
engine = PolicyEngine()
referrals = {r["referral_id"]: r for r in json.load(open("data/referral-queue.json"))}

engine.classify(referrals["RF-2026-0412"])   # success: autonomous
engine.classify(referrals["RF-2026-0415"])   # edge: direct restricted trigger
engine.classify(referrals["RF-2026-0422"])   # edge: disguised — label says "draft note", summary says reinstate
engine.classify({"referral_id": "T", "requested_action": "Do something odd", "summary": "Unrecognisable."})  # edge: fail-safe
```

| Case | Result |
|---|---|
| Routine review (RF-2026-0412) | `status='autonomous'`, `matched_rules=[]` |
| Direct trigger, e.g. "Suspend..." (RF-2026-0415) | `status='requires_approval'`, matched `['3.2']` |
| Disguised (RF-2026-0422 — `requested_action` reads "Draft triage note for supervisor", but the summary describes a reinstatement) | `status='requires_approval'`, matched `['3.2']` — proof `classify()` reads `summary` too, not just the label |
| Unrecognised text, no restricted trigger and no safe pattern | `status='requires_approval'`, `matched_rules=[]` — policy 6.1's fail-safe: unclear defaults to requiring approval, never to autonomous |

### 2.3 `agent/policy_engine.py` — `PolicyEngine.check_household_restriction()`

```python
engine.check_household_restriction({"household": [{"name": "A", "date_of_birth": "1980-01-01", "relationship": "Applicant"}]})  # success: clear
engine.check_household_restriction({"household": [{"name": "Kid", "date_of_birth": "2020-01-01", "relationship": "Son/daughter"}]})  # edge: minor present
engine.check_household_restriction(None)                    # edge: resident unfetchable
engine.check_household_restriction({"resident_ref": "X"})   # edge: record present, no "household" key
engine.check_household_restriction({"household": []})       # edge: household known, and it's empty
```

| Case | Result |
|---|---|
| Household with no one under 18 | `status='clear'` |
| Household includes a minor | `status='handoff_required'`, reason names them and their age |
| `resident=None` (history fetch failed entirely) | `status='handoff_required'` — clause 5.2: unknown composition is treated as 3.9 applying |
| Resident record present but has no `household` key | `status='handoff_required'` — same fail-safe; "we don't know" is not "there are none" |
| `household: []` (known, and genuinely empty) | `status='clear'` — this is the one case that's the *opposite* of the row above: an empty list is a known fact, not missing data, so no minor is possible and 3.9 doesn't apply |

### 2.4 `agent/approval_gate.py` — `ApprovalGate`

```python
import tempfile, sys; sys.path.insert(0, "agent")
from approval_gate import ApprovalGate, ApprovalRequiredError
gate = ApprovalGate(tempfile.mktemp(suffix=".json"))

gate.apply_restricted_action("RF-TEST", rule_ids=["3.2"])          # edge: raises, unapproved
gate.record_approval("RF-TEST", approved_by="J. Wren")
gate.apply_restricted_action("RF-TEST", rule_ids=["3.2"])          # success: now proceeds
gate.apply_restricted_action("RF-OTHER", rule_ids=["3.4"])         # edge: a different referral is still blocked
gate.record_approval("RF-TEST", approved_by="Someone Else")        # edge: duplicate approval
```

| Case | Result |
|---|---|
| Unapproved referral | Raises `ApprovalRequiredError` every time — this is the floor's "hard gate," demonstrated as a negative, not just described |
| Approved referral | Returns a dict confirming clearance; performs no mutation itself (there's nothing in this codebase for it to mutate — see `history_client.py`) |
| A second, different referral, never approved | Still raises — the gate is per-referral, not a global switch |
| Approving the same referral twice | No error, and `approvals.json` still holds exactly one record for it (`record_approval()` checks before appending) |

### 2.5 `agent/triage.py` — the three output functions

```python
import tempfile, os, json, sys; sys.path.insert(0, "agent")
import triage
from policy_engine import PolicyEngine
engine = PolicyEngine()
tmp = tempfile.mkdtemp()
referral = {"referral_id": "RF-TEST", "resident_ref": "R-TEST", "received_at": "2026-03-17T09:00:00",
            "source": "Test", "summary": "...", "requested_action": "Review award", "urgency": "Standard"}
resident = {"status": "Active", "benefit_code": "HSP-A", "district": "Test", "award_monthly": 500.0,
            "household": [{"name": "A", "date_of_birth": "1980-01-01", "relationship": "Applicant"}], "events": []}

triage.draft_triage_note(referral, resident, os.path.join(tmp, "notes"))
triage.write_escalation(referral, None, engine.classify({**referral, "summary": "Suspend the award."}), os.path.join(tmp, "escalations"))  # edge: resident=None
triage.write_handoff(referral, resident, engine.check_household_restriction({"household": [{"name": "Kid", "date_of_birth": "2020-01-01", "relationship": "Son/daughter"}]}), os.path.join(tmp, "handoffs"))
```

| Case | Result |
|---|---|
| `draft_triage_note` | A `.txt` file: situation, requested action, household/case-history context, and an explicit "this is a proposal" line. |
| `write_escalation`, resident fetched normally | `.json`: `record_type='escalation'`, `status='AWAITING_SUPERVISOR_APPROVAL'`, full `resident_context`. |
| `write_escalation`, `resident=None` (edge case — the fetch failed but the referral's *text* still classified as restricted) | Same record, but `resident_context` is all-null with an explicit `"note": "Resident history could not be retrieved."` rather than crashing or omitting the field. |
| `write_handoff` | `.json`: `record_type='hand_off'`, `status='HANDED_OFF_TO_CASEWORKER'`, `agent_action_taken` states plainly that no note was drafted. Written to its own directory — never call this with the same `out_dir` as `write_escalation`. |

### 2.6 `agent/trace.py` — `Trace`

Not usually called standalone — every `run_agent.py run` exercises it.
To check directly: `output/trace.jsonl` after any `run` should be valid
JSON Lines (`python3 -c "import json; [json.loads(l) for l in open('output/trace.jsonl')]"` — raises on the first malformed line, prints nothing on success), and every line should carry a `ts` and an `event` key at minimum.

## 3. CLI-level flow and edge cases (`agent/run_agent.py`)

These go through a real subprocess and real files, so they're not in the
automated suite — check them by hand, in this order:

```bash
# 1. Empty-state messages, before any run has happened
python3 agent/run_agent.py list-pending    # -> "No escalations yet -- run `run` first."
python3 agent/run_agent.py list-handoffs   # -> "No hand-offs yet -- run `run` first."

# 2. The full run, success path
python3 agent/run_agent.py run
# -> Done. 5 drafted autonomously, 4 escalated for supervisor approval,
#    3 handed off to a caseworker (amendment ACA-2026/2).

# 3. Listings after a run
python3 agent/run_agent.py list-pending     # -> 4 entries: RF-2026-0415/0419/0422/0423
python3 agent/run_agent.py list-handoffs    # -> 3 entries: RF-2026-0412/0416/0418

# 4. Approve one, then re-list — it should drop out
python3 agent/run_agent.py approve RF-2026-0415 --by "J. Wren" --note "Reviewed, cleared."
python3 agent/run_agent.py list-pending     # -> now only 3 entries; RF-2026-0415 is gone

# 5. Edge: approve an unknown referral
python3 agent/run_agent.py approve RF-DOES-NOT-EXIST --by "Test"
# -> "No escalation found for RF-DOES-NOT-EXIST. Run `list-pending` to
#     see what's outstanding." — exits non-zero (exit code 1)

# 6. Edge: approve the same referral twice
python3 agent/run_agent.py approve RF-2026-0415 --by "Someone Else"
# -> succeeds again, silently (record_approval() is idempotent);
#    approvals.json still has exactly one record for RF-2026-0415

# 7. Edge: the mock service is unreachable for the whole run
python3 agent/run_agent.py --history-url http://127.0.0.1:9 run
# -> Done. 0 drafted autonomously, 4 escalated for supervisor approval,
#    8 handed off to a caseworker (amendment ACA-2026/2).
#    (12 history fetch(es) failed -- handled via escalation or
#    hand-off above, not dropped.)
# All 12 referrals still accounted for: nothing silently disappears.
# The 4 escalations are unaffected (classify() never needed resident
# data); the 8 that would normally draft autonomously all hand off
# instead, per clause 5.2.
```

Before re-running from a clean state, clear the generated output (this
is safe — everything in `output/` and `approvals/approvals.json` is
regenerated by `run`):

```bash
rm -f output/triage_notes/*.txt output/escalations/*.json output/handoffs/*.json output/trace.jsonl approvals/approvals.json
```

## 4. Full demo sequence

The shortest path that exercises every floor requirement and the
amendment in one pass:

```bash
# terminal 1
python3 services/history_service.py --port 8083

# terminal 2
python3 agent/run_agent.py run              # full 3-outcome run
python3 agent/run_agent.py list-pending     # escalation queue
python3 agent/run_agent.py list-handoffs    # amendment hand-offs
python3 agent/run_agent.py approve RF-2026-0415 --by "J. Wren"
python3 agent/run_agent.py list-pending     # confirm it dropped out
cat output/trace.jsonl                      # the execution trace
python3 -m unittest discover -s tests -v    # 24/24 tests
```

## 5. Clean-clone check

The floor's last item is "runs from a clean clone using the README
alone." To verify it directly rather than assume it:

```bash
git clone <this repo> /tmp/clean-check
cd /tmp/clean-check
python -m venv .venv && .venv\Scripts\Activate.ps1    # per README
python3 services/history_service.py --port 8083 &
python3 agent/run_agent.py run
python3 -m unittest discover -s tests -v
```
