"""
MODULE 6 — Triage note drafting & escalation records.

Two outputs, both non-mutating (policy 2.4: "A drafted note is a proposal.
It has no effect on the case until a caseworker adopts it."):

1. draft_triage_note(referral, resident, out_dir) -> path
   For a referral classified "autonomous". Should read like something a
   caseworker can act on directly: the situation, the requested action,
   relevant household/case-history context pulled from the resident
   record (Module 2's output), and a clear "this is a proposal, not
   applied" note. Write it to out_dir/<referral_id>.txt (or .md).

2. write_escalation(referral, resident, decision, out_dir) -> path
   For a referral classified "requires_approval". Policy 4.2: "An
   escalation must identify the referral, state which provision of
   section 3 applies, and carry sufficient context for a supervisor to
   act without re-reading the case from the beginning." So include: the
   referral fields, which rule(s) from the Decision matched (Module 3),
   the policy engine's reason string, relevant resident context, and an
   explicit status like "AWAITING_SUPERVISOR_APPROVAL". Write it to
   out_dir/<referral_id>.json — structured, since Module 7's
   `list-pending` command and Module 5's approval flow both need to read
   it back.

Neither function should perform or prepare the restricted action itself
(policy 4.1) — they only ever describe it.
"""

# TODO: implement draft_triage_note and write_escalation
