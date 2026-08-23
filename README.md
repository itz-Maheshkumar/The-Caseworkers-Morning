# The-Caseworkers-Morning

An AI agent that automates a caseworker's overnight-referral triage —
read the referral, pull the resident's history, draft a triage note — and
stops to get supervisor approval before touching anything the authority
policy reserves for a human.

Built for the "Agentic AI / Guardrails" problem: **Problem 5 — The
Caseworker's Morning**. Full brief in `docs/` (not committed — see the
original problem pack) — the short version: chaining three steps together
isn't the hard part. Knowing which of those steps the agent isn't allowed
to take alone, and *proving* the boundary is enforced rather than just
requested, is the hard part.

## Status

Modules 1–8 built and tested — the floor is functionally met end to end
(`run` → `list-pending` → `approve`, against the real mock API and the
real 12-referral queue), and locked in by 14 automated tests covering the
classifier and the approval gate. Module 9 (finish the docs) is what's
left.

## The floor (what "done" means)

- [x] A three-step agent run that completes for every referral it's
      permitted to handle. — `run` processes all 12 referrals: 8 drafted,
      4 escalated.
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

## Design principles carried through every module

1. **Policy is data, not code.** The authority boundary (policy
   ACA-2026/1) lives in `data/policy_rules.json`. No module should contain
   hard-coded policy text — only logic for *applying* whatever the data
   file says. This is the direct answer to the brief's warning that
   requirements change on "day two" without notice: a policy change should
   be a data edit, not a code change.
2. **The mutating capability shouldn't exist, not just be forbidden.**
   `services/history_service.py` only exposes `GET` routes. As long as
   nothing in `agent/` adds a way to write back to a resident's record,
   the agent is structurally incapable of the Section 3 actions — that's
   a stronger guarantee than "the agent was told not to."
3. **A drafted note or an escalation is the only output.** Neither
   mutates anything. A triage note is a proposal until a caseworker
   adopts it; an escalation is a request for a supervisor to look, not an
   attempt to act.

## Project structure

```
The-Caseworkers-Morning/
├── README.md                       — this file
├── DECISIONS.md                    — fill in as modules land
├── AI-USAGE.md                     — fill in as modules land
├── data/
│   ├── referral-queue.json         — given: 12 overnight referrals
│   ├── authority-policy.md         — given: policy ACA-2026/1 (human-readable)
│   └── policy_rules.json           — MODULE 1: same policy, as structured data
├── services/
│   ├── history_service.py          — given: mock Resident History API
│   └── _history_data.json          — given: the data it serves
├── agent/
│   ├── history_client.py           — MODULE 2: client for the history API
│   ├── policy_engine.py            — MODULE 3: classify referral -> autonomous | requires_approval
│   ├── trace.py                    — MODULE 4: execution trace (policy 5.1/5.2)
│   ├── approval_gate.py            — MODULE 5: the hard approval gate
│   ├── triage.py                   — MODULE 6: draft notes + escalation records
│   └── run_agent.py                — MODULE 7: CLI / orchestrator, ties 1-6 together
├── tests/
│   └── test_policy_engine.py       — MODULE 8: verification
├── approvals/                      — approvals.json lands here at runtime
└── output/
    ├── trace.jsonl                 — generated at runtime
    ├── triage_notes/                — generated at runtime
    └── escalations/                 — generated at runtime
```

Files marked "given" are the unmodified problem pack — data and fixtures,
not something to edit. Everything under `agent/` is a stub right now: each
one has a docstring laying out its contract (inputs, outputs, which policy
clause it's responsible for) and a `# TODO`.

## Development plan — module by module

Build in this order; each module is usable/testable on its own before the
next one needs it.

**Module 1 — Policy as data** (`data/policy_rules.json`)
Encode `data/authority-policy.md` as structured rules: which actions are
autonomous (Section 2), which need approval (Section 3, with trigger
phrases per action), and the fail-safe default for anything unclear
(Section 6.1). Done when: the file fully represents the policy and nothing
else needs to read the `.md` file at runtime.

**Module 2 — History client** (`agent/history_client.py`)
Thin wrapper around the mock API's `GET` endpoints. Done when: it can
fetch a full resident record, household, and events, standard library
only, with `services/history_service.py` running locally.

**Module 3 — Policy engine** (`agent/policy_engine.py`)
Classify a referral against `policy_rules.json`, checking *both*
`requested_action` and `summary` (not just the label a referral was given).
Done when: run against all 12 referrals in `data/referral-queue.json` and
manually check each classification against the policy — including the one
where the requested action *sounds* fine but the summary isn't.

**Module 4 — Trace** (`agent/trace.py`)
Structured, timestamped log of every step. Done when: a person who wasn't
in the room can read `output/trace.jsonl` and reconstruct the whole run.

**Module 5 — Approval gate** (`agent/approval_gate.py`)
The hard gate: a restricted action cannot proceed without a prior,
human-written approval record. Done when: you can demonstrate the negative
— call the gated function on something unapproved and watch it refuse.

**Module 6 — Triage & escalation drafting** (`agent/triage.py`)
Turn a classified referral + resident record into either a triage note
(autonomous) or an escalation record with enough context for a supervisor
to act without re-reading the case (Section 4.2). Done when: both output
types read like something a real caseworker/supervisor could use as-is.

**Module 7 — Orchestrator / CLI** (`agent/run_agent.py`)
Wire Modules 1-6 into `run`, `list-pending`, and `approve` commands. One
referral escalating or failing must never stop the rest of the queue.
Done when: a clean clone + this README is enough for someone else to run
the whole thing.

**Module 8 — Tests** (`tests/`)
Lock in the classification behaviour and the gate's refusal behaviour
before touching anything else — cheap insurance against the "day two"
requirement change breaking something silently.

**Module 9 — Docs** (`DECISIONS.md`, `AI-USAGE.md`)
Not a separate coding module, but don't leave it to the end — fill in each
file's relevant section as the module it describes gets built, while the
reasoning is still fresh.

## Environment setup

A `.venv` keeps anything installed for this project separate from your
system Python — do this once, before Module 1:

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
never gets committed. Right now the project needs nothing beyond the
standard library, so there's nothing to `pip install` yet — but as
modules bring in real dependencies, install them with the venv active and
run `pip freeze > requirements.txt` to lock them, so a clean clone can
recreate the same environment with `pip install -r requirements.txt`.
Deactivate anytime with `deactivate`.

## Running it (once built)

Make sure the `.venv` is active first (see above).

```bash
# terminal 1
python3 services/history_service.py --port 8083

# terminal 2
python3 agent/run_agent.py run
python3 agent/run_agent.py list-pending
python3 agent/run_agent.py approve <referral_id> --by "<name>"
```

Python 3, standard library only for now — no dependencies to install yet.

## Running the tests

```bash
python3 -m unittest discover -s tests -v
```

No mock service needed — the tests exercise `policy_engine.py` and
`approval_gate.py` directly against the real `data/` files, not against a
running server.
