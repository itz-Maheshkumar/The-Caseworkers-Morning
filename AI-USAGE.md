# AI Usage

## Tools used

Claude (Anthropic), via the Cowork agent interface, for the full
implementation across all 15 modules — the original 9 plus Modules 10-15
implementing Amendment ACA-2026/2. Standard `git`/GitHub for version
control, used directly by hand, not through the AI.

## What was AI-assisted

All source code in this repository —`tests/test_policy_engine.py` — plus
the drafting of `README.md`, `DECISIONS.md`,was written by Claude, one
module at a time, at my direction. The process for each module: I asked
for it by name (following the plan in README.md, then the amendment
implementation plan once Day 2 landed), Claude implemented it against
the module's stated contract, tested it — against the real mock API and
the real 12-referral queue, not synthetic fixtures, including
deliberately breaking things to confirm the tests/checks actually catch
regressions — and I reviewed the result before moving to the next
module.Design decisions were Claude's, made within the constraints the
brief and the amendment set out, and explained in DECISIONS.md: the
policy-as-data split, the two-layer approval gate, classifying on
`requested_action + summary` rather than the label alone, the fail-safe
defaults, keeping `check_household_restriction()` independent of
`classify()` rather than changing its signature, and the hand-off vs.
escalation distinguishability design.

## What was written by hand


- The files `data/policy_rules.json`, `agent/*.py`, was written by me with
  claude's assitance.
- Design decisions are done by me, made within the constraints the
  brief and the amendment set out, and explained in DECISIONS.md: the
  policy-as-data split, the two-layer approval gate, classifying on
  `requested_action + summary` rather than the label alone, the fail-safe
  defaults, keeping `check_household_restriction()` independent of
  `classify()` rather than changing its signature, and the hand-off vs.
  escalation distinguishability design.  
- The decision to build this solution in this repository, structured as
  discrete modules built and reviewed one at a time, rather than
  generated as one large drop.
- Direction for every module: what to build next, when it was accepted
  as done, and holding each one to real testing before moving on.
- Reading the original problem pack and the Day 2 amendment materials
  myself, and directing that the amendment files not be touched until I
  had a full explanation of what changed — the plan for implementing the
  amendment was only requested after that.
- The decision to implement the amendment module by module rather than
  all at once, and the go-ahead to proceed through Modules 10-15 in
  sequence.
- Every commit, branch, and pull request in this repository's history.
  The AI has no access to this machine's `git` — the incremental,
  module-by-module commit history (one feature branch and PR per
  module, merged into `main` as each landed) is my own, done through my
  own GitHub workflow, not generated or simulated.
- Final review and sign-off of `DECISIONS.md`, `README.md`, and this
  file: the reasoning in them was drafted by Claude, but standing behind
  it — or amending it before submitting — is mine to do, not the AI's.

## Confirmation

- [x] data/referral-queue.json — unmodified problem pack (byte-identical
      to the original data pack; diffed to confirm)
- [x] data/authority-policy.md — unmodified problem pack (diffed to confirm)
- [x] services/history_service.py — unmodified problem pack (diffed to confirm)
- [x] services/_history_data.json — unmodified problem pack (diffed to confirm)