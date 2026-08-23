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

**Replace exact-substring trigger matching with something more robust**
(stemming, fuzzy matching, or a small classifier), while keeping the same
contract: policy content stays in `policy_rules.json`, and anything below
a confidence threshold still defaults to `requires_approval`. The current
matching is deliberately simple and auditable — a supervisor can read
`policy_rules.json` and know exactly why a referral was flagged — but it's
also brittle to phrasing the trigger lists didn't anticipate. That
brittleness is caught by the fail-safe default (Section 6.1), not
eliminated by it, so a referral worded unusually enough to dodge both the
restricted triggers *and* the recognised-safe patterns still escalates
correctly — but a referral that happens to land inside a safe pattern by
accident wouldn't. Widening `recognised_safe_actions` cautiously, or
requiring a higher bar of specificity before something counts as "safe,"
is the direction to push.

**Persist run state so a crashed run can resume.** Right now a run that
dies mid-queue (not from a single referral's history-fetch failure, which
is already handled, but from something crashing `run_agent.py` itself —
e.g. the mock service going down entirely) has to restart from referral
one. The trace already records exactly what was done in what order; the
missing piece is checking, on startup, which referral IDs already have a
triage note or escalation record and skipping them.

**A real notification path for `list-pending`.** Explicitly out of scope
per the brief ("not required: a real approval workflow with notifications
and accounts"), but the escalation record schema (`triage.py`'s
`write_escalation`) was written with this in mind — every field a
notifier would need (referral, resident context, matched rule, reason) is
already there, so bolting one on wouldn't require changing the schema,
just adding a consumer of it.

**Handle the "day two" change when it lands**, obviously — this is the
one item on this list that isn't optional. The whole point of Modules 1
and 3 being split the way they are is that the day-two change should be
absorbable without this file needing a new "what broke" section.

## Amendment ACA-2026/2 — what changed, what didn't, and what I'd do differently

The amendment's own `READ ME FIRST` asks for this entry explicitly, so
this is written as an update, not folded silently into the sections
above.

**What changed.** One new fail-safe rule, clause 3.9: a household that
includes anyone under 18 gets no triage note drafted at all — not "don't
adopt it," "don't produce it." That's encoded as a new
`household_restrictions` block in `data/policy_rules.json` (Module 10), a
new `PolicyEngine.check_household_restriction()` method (Module 11), a new
`triage.write_handoff()` output (Module 12) written to its own
`output/handoffs/` directory, and `run_agent.py`'s `cmd_run()` gaining a
third branch so the order per referral is now: classify on text →
if `requires_approval`, escalate as before → if `autonomous`, check the
household → `handoff_required` writes a hand-off, otherwise draft as
before (Module 13). Checked against the real queue: RF-2026-0412 (age 5),
RF-2026-0416 (age 3), and RF-2026-0418 (ages 12 and 0) are exactly the
three referrals affected — confirmed by computing ages from
`services/_history_data.json` against the referral batch date, not by
guessing from the data pack's own hints.

**What was deliberately left alone.** `PolicyEngine.classify()`'s
signature, behavior, and all 14 of its Module 3/8 tests are untouched —
`check_household_restriction()` is a second, independent method rather
than a parameter added to `classify()`. `triage.draft_triage_note()` and
`write_escalation()` are untouched in behavior (`write_escalation()`
gained an optional `resident=None` default and a `record_type` field, but
produces byte-for-byte the same content it did before for every referral
that isn't affected by the amendment). No existing output directory or
file format changed shape.

**What I'd do differently with foreknowledge.** `classify()` would take
the resident record as an input from the start — a single decision point
returning one of `autonomous` / `requires_approval` / `handoff_required`,
rather than two decision points a caller has to sequence correctly by
hand. That would have made Module 11 unnecessary as a bolted-on second
path and removed the risk (avoided here only by testing it directly) of
`run_agent.py` checking the household restriction in the wrong order
relative to the text classification, or forgetting to check it at all for
one of the three outcomes. The reason it wasn't built that way from day
one is that day one had no way to know a second, independent axis of
restriction was coming — which is itself the point of Section 6's
literal "day two" warning, and exactly the kind of code-shaped change
`policy_rules.json`'s data-only design doesn't fully insulate against
(see "Why the policy lives in data/policy_rules.json instead of in
code," above: that section's design absorbed a *new rule*, 3.9, as a data
edit just fine; what it didn't and couldn't absorb as a data edit was a
new *kind* of input, resident data, into a function that was never
built to take it).

**Open interpretation call — the overlap case.** No referral in the
current queue is both Section-3-restricted and has a minor in the
household (verified directly: running `check_household_restriction()`
against all four escalated referrals' resident records returns `clear`
for all four), so this batch never actually exercises the question. The
decision made anyway: escalation takes priority, and no separate
hand-off record is produced for a referral that's already escalating —
`run_agent.py`'s `requires_approval` branch returns before the household
check ever runs. Rationale: an escalation already means no triage note
gets drafted, which is the entire effect 3.9 requires; a redundant
hand-off record would describe an action (drafting) that was never going
to happen for a second, unrelated reason, and would leave a supervisor
looking at two records for one referral without a stated rule for which
one governs. The one piece of this recommendation not implemented:
optionally noting "household includes a minor" as extra context inside
the escalation record itself. Left out because there's no case in the
current data to build or test it against, and adding an unexercised code
path felt like a worse trade than documenting the gap here. If the
organizers intended the overlap case to behave differently, this is
exactly the kind of assumption the amendment's cover note invites asking
about.

**Open interpretation call — the age reference date.** `age_years()`
(`agent/dates.py`) computes age relative to `REFERRAL_BATCH_DATE`
(`2026-03-17`), not whichever date the code happens to run on, and both
`triage.draft_triage_note()`'s age display and
`check_household_restriction()`'s 3.9 check now share that one function
and one constant. The amendment doesn't state a reference date outright;
the decision made was to reuse the same convention `triage.py` already
established for Module 6, on the reasoning that a person's age
disagreeing between two places in the same run — one honest artifact of
running the agent today, one artifact of reading a March referral — would
be a worse failure mode than picking a convention and documenting it.
