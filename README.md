# The-Caseworkers-Morning

An AI agent that automates a caseworker's overnight-referral triage —
read the referral, pull the resident's history, draft a triage note — and
stops to get supervisor approval before touching anything the authority
policy reserves for a human.

Built for the "Agentic AI / Guardrails" problem: **Problem 5 — The
Caseworker's Morning** (Brite Spark 2026). The full brief and the
authority policy it's built against are not committed to this repo — see
the original problem pack. The short version: chaining three steps
together isn't the hard part. Knowing which of those steps the agent
isn't allowed to take alone, and *proving* the boundary is enforced
rather than just requested, is the hard part.

## Status

The floor is met end to end (`run` → `list-pending` → `approve`, against
the real mock API and the real 12-referral queue), and so is Amendment
ACA-2026/2, the Day 2 policy change (`run` now also produces
`list-handoffs`; see below). All of it is locked in by 24 automated
tests and documented in DECISIONS.md / AI-USAGE.md. Still outstanding
before submission: filling in `AI-USAGE.md` (currently still the blank
template — tools used, what was AI-assisted vs. written by hand, and the
unmodified-problem-pack confirmations), and your own read-through of
everything before it ships, especially AI-USAGE.md's characterisation of
the process and DECISIONS.md's reasoning, since both are yours to stand
behind.

## The floor (what "done" means)

- [x] A three-step agent run that completes for every referral it's
      permitted to handle. — `run` processes all 12 referrals: 5
      drafted, 4 escalated, 3 handed off under Amendment ACA-2026/2 (the
      3 that move from "drafted" to "handed off" are exactly the ones
      with a minor in the household — see clause 3.9 below).
- [x] A visible execution trace — a supervisor can reconstruct, after the
      fact, what was done, in what order, on what basis, and what was
      declined. — `output/trace.jsonl`, one JSON object per step.
- [x] A **hard** approval gate on irreversible actions — code-enforced,
      not prompt-enforced. — `ApprovalGate.apply_restricted_action()`
      raises `ApprovalRequiredError` without a prior human-written record;
      verified directly, including that approving one referral leaves a
      different one still blocked.
- [x] Correct refusal + escalation of every out-of-authority referral,
      without stopping the rest of the run. — 4/12 escalate correctly
      (including the one disguised as a safe request); a synthetic
      history-fetch failure on one referral was confirmed not to affect
      the other 11.
- [x] Runs from a clean clone using this README alone. — tested by
      copying the repo to a clean directory and running `run` /
      `list-pending` / `approve` against it directly.

## Design principles

1. **Policy is data, not code.** The authority boundary (policy
   ACA-2026/1) lives in `data/policy_rules.json`. No module contains
   hard-coded policy text — only logic for *applying* whatever the data
   file says. This is the direct answer to the brief's warning that
   requirements change on "day two" without notice: a policy change is a
   data edit, not a code change.
2. **The mutating capability shouldn't exist, not just be forbidden.**
   `services/history_service.py` only exposes `GET` routes. As long as
   nothing in `agent/` adds a way to write back to a resident's record,
   the agent is structurally incapable of the Section 3 actions — that's
   a stronger guarantee than "the agent was told not to."
3. **A drafted note, an escalation, or a hand-off is the only output.**
   None of the three mutates anything. A triage note is a proposal until
   a caseworker adopts it; an escalation is a request for a supervisor to
   look, not an attempt to act; a hand-off produces nothing to adopt at
   all.

## Project structure

```
The-Caseworkers-Morning/
├── README.md                       — this file
├── DECISIONS.md                    — reasoning behind the design
├── AI-USAGE.md                     — AI-usage attestation
├── data/
│   ├── referral-queue.json         — given: 12 overnight referrals
│   ├── authority-policy.md         — given: policy ACA-2026/1 (human-readable)
│   └── policy_rules.json           — the policy, as structured data
├── services/
│   ├── history_service.py          — given: mock Resident History API
│   └── _history_data.json          — given: the data it serves
├── agent/
│   ├── history_client.py           — client for the history API
│   ├── policy_engine.py            — classify() -> autonomous | requires_approval;
│   │                                   check_household_restriction() -> clear | handoff_required
│   ├── trace.py                    — execution trace (policy 5.1/5.2)
│   ├── approval_gate.py            — the hard approval gate
│   ├── dates.py                    — shared age_years() helper
│   ├── triage.py                   — draft notes, escalation records, hand-off records
│   └── run_agent.py                — CLI / orchestrator
├── tests/
│   └── test_policy_engine.py       — 24 tests
├── approvals/                      — approvals.json lands here at runtime
└── output/
    ├── trace.jsonl                 — generated at runtime
    ├── triage_notes/                — generated at runtime
    ├── escalations/                 — generated at runtime
    └── handoffs/                    — generated at runtime
```

Files marked "given" are the unmodified problem pack — data and
fixtures, not something to edit. Each file under `agent/` has a
docstring doubling as its contract (inputs, outputs, which policy clause
it's responsible for).

## Amendment ACA-2026/2 (Day 2)

A policy amendment landed after the original brief: drafting a triage
note is no longer permitted at all for a referral concerning a household
that includes anyone under 18 (clause 3.9) — not "don't adopt it," "don't
produce it in the first place." The agent hands those referrals to a
caseworker instead: `agent/triage.write_handoff()` writes a record to
`output/handoffs/`, distinct from `output/escalations/`, because a
hand-off is ordinary casework a person must do, not a decision the
Department must authorise. `list-handoffs` shows them. A resident whose
history couldn't be fetched at all is treated as household composition
unknown, and therefore also handed off rather than drafted or silently
dropped.

See `DECISIONS.md` for what changed, what was deliberately left alone,
and the two interpretation calls the amendment doesn't settle outright
(what happens when a referral is both Section-3-restricted and has a
minor in the household; which reference date "age" is computed against).

## Environment setup

A `.venv` keeps anything installed for this project separate from your
system Python:

```powershell
# from the repo root, in PowerShell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

```bat
:: same, from cmd.exe
python -m venv .venv
.venv\Scripts\activate.bat
```

Your prompt should then show `(.venv)`. `.venv/` is git-ignored, so it
never gets committed. The project needs nothing beyond the standard
library, so there's nothing to `pip install` — `requirements.txt` is
present but empty, ready for `pip freeze` if that ever changes. Deactivate
anytime with `deactivate`.

## Running it

Make sure the `.venv` is active first (see above).

```bash
# terminal 1
python3 services/history_service.py --port 8083

# terminal 2
python3 agent/run_agent.py run
python3 agent/run_agent.py list-pending
python3 agent/run_agent.py list-handoffs
python3 agent/run_agent.py approve <referral_id> --by "<name>"
```

Python 3, standard library only — no dependencies to install.

## Running the tests

```bash
python3 -m unittest discover -s tests -v
```

No mock service needed — the tests exercise `policy_engine.py`,
`approval_gate.py`, and `triage.py` directly against the real `data/`
files, not against a running server.
