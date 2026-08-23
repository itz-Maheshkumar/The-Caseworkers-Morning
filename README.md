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

All 9 modules built and tested. The floor is met end to end (`run` →
`list-pending` → `approve`, against the real mock API and the real
12-referral queue), locked in by 14 automated tests, and documented in
DECISIONS.md / AI-USAGE.md. Still outstanding before submission: real
incremental git commits (this was built and pushed in large steps, not
committed as it went — see AI-USAGE.md), and your own read-through of
everything before it ships, especially AI-USAGE.md's characterisation of
the process and DECISIONS.md's reasoning, since both are yours to stand
behind.

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

## Amendment ACA-2026/2 — implementation plan (Day 2)

The day-two change landed: **Amendment ACA-2026/2** inserts a new clause,
**3.9**, into the authority policy — drafting a triage note is no longer
permitted *at all* for a referral concerning a household that includes
anyone under 18. Not "don't adopt it" — "don't produce the draft in the
first place." What happens instead is a **hand-off**, which the amendment
is explicit must be distinguishable from an escalation: an escalation
means "the Department must decide whether this may happen at all"; a
hand-off means "this is ordinary casework a person must do."

Checked against the real queue: **RF-2026-0412, RF-2026-0416, and
RF-2026-0418** each have a minor in the household (ages 5, 3, and 12 & 0 respectively)
and currently get drafted as autonomous. Those three need to stop being
drafted and start being handed off instead. None of the 4 already-escalated
referrals (0415/0419/0422/0423) have a minor in the household, so in this
batch the two rule systems don't overlap — but the design still has to
decide what *would* happen if they did (see "Open interpretation calls"
below).

This is a genuinely different kind of rule from Sections 3.1–3.8: those
are evaluated from the referral's own text (`requested_action` + `summary`);
3.9 is evaluated from the resident's household composition — data the
current `policy_engine.classify()` never looks at. That's the real test of
whether "policy is data, not code" holds up, or whether it turns out to
have been implicitly scoped to text-matching only.

**Module 10 — Encode 3.9 as data** (`data/policy_rules.json`)
Add a new top-level section, separate from `restricted_actions`, since
this is evaluated against resident data, not referral text — e.g.
`household_restrictions: [{id: "3.9", age_threshold_years: 18,
on_composition_unknown: "treat_as_applying"}]`, the last field encoding
amendment 5.2's fail-safe (household composition unknown → treat 3.9 as
applying) the same way `default_when_unclear` already encodes 6.1's.
Done when: nothing about age 18, or what to do when composition is
unknown, exists anywhere outside this file.

**Module 11 — Household-composition check** (`agent/policy_engine.py`)
A new function — not a change to `classify()`'s existing signature, to
avoid disturbing Module 3's contract and its passing tests — that takes a
resident record (or `None`, if history couldn't be fetched) and returns
whether 3.9 applies, reusing the `Decision`-style shape (status,
matched rule `3.9`, reason naming which household member triggered it)
so downstream code doesn't need a second decision shape to handle. Done
when: it correctly flags all three known cases (0412, 0416, 0418), leaves
the other 9 unflagged, and returns "applies" (not "unknown") when handed
`None`.

**Module 12 — The hand-off output type** (`agent/triage.py`)
A third function, `write_handoff()`, alongside the existing
`draft_triage_note()` / `write_escalation()`. No note text is generated —
none is allowed to exist per 2.2. The record carries whatever was already
established (referral fields, resident/household context if fetched) so
the caseworker doesn't repeat work (3.2/4.2), with a status string
(e.g. `HANDED_OFF_TO_CASEWORKER`) distinct from escalation's
`AWAITING_SUPERVISOR_APPROVAL`, written to a **separate directory**
(`output/handoffs/`) rather than reusing `output/escalations/` — physical
separation is the simplest way to make "distinguishable from an
escalation" (3.3) not rely on someone reading a status field carefully.

**Module 13 — Orchestrator: three-way branch + the fetch-failure fail-safe**
(`agent/run_agent.py`)
Per referral, the order becomes: fetch history → run the existing text
classifier regardless of whether the fetch succeeded (it doesn't need
resident data) → then:
- `requires_approval` → escalate, as today (unaffected by 3.9 — an
  escalation already means no note gets drafted, so 3.9 is moot here);
- `autonomous` **and** history fetch failed → hand off, citing 5.2
  (composition unknown → treat 3.9 as applying) — this is a real behavior
  change: today a fetch failure just gets logged and nothing is produced;
  after this amendment it must produce a hand-off, because "no output at
  all" isn't the same as "handed to the caseworker with what's known" (4.2
  requires the latter);
- `autonomous` **and** a minor is in the household → hand off, citing 3.9;
- `autonomous` and neither → draft the note, as today.

Also needs: a new trace event type for the hand-off decision, updated run
summary counts (autonomous / escalated / handed off / failed), and a
`list-handoffs` CLI command as a sibling to `list-pending` — kept separate
rather than folded into one listing, again for 3.3's distinguishability.
Done when: `run` against the real queue produces exactly 3 hand-offs (plus
the existing 4 escalations and 5 remaining autonomous drafts), and a
synthetic fetch failure on an otherwise-autonomous referral produces a
hand-off instead of silently disappearing.

**Module 14 — Tests for the amendment** (`tests/`)
Cover: each of the three known 3.9 cases produces a hand-off and *no*
triage-note file; the 4 existing escalations are unaffected; a fetch
failure on an otherwise-autonomous referral produces a hand-off citing 5.2
rather than just incrementing a `failed` counter; a hand-off record and an
escalation record are structurally distinguishable (different `status`
value, different directory) by assertion, not just by inspection.

**Module 15 — The required `DECISIONS.md` entry**
The amendment's own `READ ME FIRST` asks for this explicitly: what
changed, what was deliberately left alone, and what would have been done
differently with foreknowledge (the honest answer is probably that
`classify()` would have taken the resident record from the start, rather
than Module 11 needing to exist as a bolted-on second decision path).
Also where the "open interpretation calls" below get written down as
decisions, not left implicit.

### Open interpretation calls (worth deciding deliberately, not by accident)

**The overlap case.** No referral in the current queue is both
Section-3-restricted *and* has a minor in the household, but the design
still has to pick a behavior for if one existed. Recommendation: escalation
takes priority and no separate hand-off is produced — an escalation
already means no note gets drafted, which is all 3.9 actually requires,
so a redundant hand-off would just be noise. Worth optionally noting
"household includes a minor" as extra context inside the escalation
record rather than acting on it separately. This is exactly the kind of
question the amendment's cover note says is fair to ask the organizers
about, if there's any doubt about it.

**Age reference date.** `triage.py` already computes age relative to the
referral batch date (`2026-03-17`), not "whenever the code happens to
run." Recommendation: reuse that same convention for 3.9 so an age
computed for the same person doesn't disagree between two different
places in the codebase — but it's an assumption, not something the
amendment states outright, and worth a line in DECISIONS.md either way.

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
