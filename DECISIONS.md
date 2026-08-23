# Decisions

_Fill this in as the modules get built — don't leave it for the end. The
brief specifically asks: "what your agent is structurally incapable of
doing without a human, and how you know. Not what you told it not to do —
what it cannot do." That means this file needs a real answer pointing at
specific code (e.g. "there is no POST/PUT/DELETE handler in
history_client.py or anywhere else — grep confirms it"), not a restatement
of the policy._

## What the agent is structurally incapable of doing without a human, and how I know

The agent cannot change a resident's award, eligibility, payment, or
payment details, communicate with a resident or third party, disclose
resident information externally, or record a finding about a resident's
conduct — **on its own** — for two independent reasons. Either would hold
even if the other failed.

**1. There is no function in this codebase that performs any of those
actions.** `agent/history_client.py` (Module 2) is the only thing this
agent talks to, and it has exactly four methods —
`get_resident`/`get_household`/`get_events`/`health` — all routed through
one private `_get()` that only ever calls `urllib.request.urlopen` against
a `GET`. `services/history_service.py` (given, unmodified) implements
`do_GET` and nothing else — grep it for `do_POST`, `do_PUT`, or
`do_DELETE` and there isn't one. There is no database connection, no other
network call, no filesystem write to anything resembling a case record,
anywhere under `agent/`. This isn't a policy the agent follows; it's the
absence of a capability, the same way a process with no socket permissions
can't exfiltrate data over the network regardless of what it's told.

**2. Even the one function that stands in for "trigger a real mutation"
refuses to run without prior human sign-off.** `agent/approval_gate.py`'s
`apply_restricted_action()` calls `require_approval()` first, which raises
`ApprovalRequiredError` unless a matching record already exists in
`approvals/approvals.json` — and the only function that writes to that
file, `record_approval()`, is called from nowhere in this repo except the
`approve` CLI subcommand `run_agent.py` will expose (a human running a
command), never from the agent's own decision loop. Verified directly, not
just asserted in this doc: calling `apply_restricted_action()` against an
unapproved referral raises every time; approving referral A leaves referral
B still blocked; and a duplicate approval doesn't create a duplicate
record. All three checks pass as of Module 5.

Point 1 is the real guarantee — it holds even against a differently
written agent loop, a bug, or a future contributor who forgets the gate
exists. Point 2 exists because the floor asks for a *demonstrable* gate,
not just an architectural argument, and because a real deployment (with a
real, writable case-management system behind it) would need an explicit
gate even where this mock setup doesn't strictly require one today.

## Why the policy lives in data/policy_rules.json instead of in code

The brief warns that a "day two" requirement change is coming and won't
be announced in advance. `agent/policy_engine.py` has no policy content in
it at all — no section numbers, no trigger phrases, no rule text. It only
knows two things, generically: how to match `requested_action` + `summary`
against whatever `restricted_actions[].triggers` exist in
`data/policy_rules.json`, and what to do when nothing matches
(`default_when_unclear`, also read from the file). Adding a new Section 3
category, changing a trigger phrase, or even flipping the fail-safe
default is a data edit to `policy_rules.json` — `policy_engine.py` doesn't
change, and nothing that imports it needs to change either. If day two
turns out to be a code-shaped change instead of a data-shaped one, that's
useful information in itself about where this design's boundary is.

## Notable classification calls and why

**RF-2026-0422** is the one worth pointing at. Its `requested_action`
field literally reads "Draft triage note for supervisor" — on its own,
that's a Section 2.4 action, permitted. A classifier that only looked at
`requested_action` would draft it and move on. But `policy_engine.py`
classifies on `requested_action + summary` together (see `classify()`),
and the summary describes an award being "reinstated from date of
termination" — a 3.2 action. Tested directly:
`classify(RF-2026-0422).status == "requires_approval"`, matched rule
`3.2`. This is the concrete answer to the data pack's own warning not to
assume "the referrals which matter announce themselves."

**RF-2026-0419** ("Record income change") is the other borderline one.
It reads like routine record-keeping, similar in shape to "Record change
of address" (RF-2026-0413, which *is* autonomous). The difference: an
income change can feed directly into the award calculation, so
`policy_rules.json` lists it under 3.1 (entitlement/award change) rather
than treating it as safe. Whether that's the *only* correct reading is
arguable — which is exactly why, if it turned out to be wrong, the fix is
removing one trigger phrase from the data file, not touching the
classifier.

**Fail-safe default, verified directly.** A referral matching neither a
restricted trigger nor a recognised-safe pattern
(`{"requested_action": "Do something unusual", ...}`) classifies as
`requires_approval`, not `autonomous` — confirmed with an assertion, not
just read off the code. Given the trigger lists in `policy_rules.json`
are necessarily incomplete, this default is what keeps an unanticipated
phrasing from silently sailing through as autonomous.

## What I'd do with more time

(Optional, but worth having if the floor is met early.)
