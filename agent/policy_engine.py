"""
MODULE 3 — Policy engine.

The only module that reasons about the Section 2 / Section 3 boundary, and
it should do so entirely by reading data/policy_rules.json — no policy
content (trigger words, section numbers, the "default when unclear" rule)
should be hard-coded here. If the policy changes (including the "day two"
change mentioned in the brief), the fix should be an edit to
policy_rules.json, not to this file.

Contract:

    class Decision:
        status: "autonomous" | "requires_approval"
        matched_rules: list[dict]   # the restricted_actions entries matched, if any
        reason: str                 # human-readable, goes straight into the trace
                                     # and into escalation records

    class PolicyEngine:
        def __init__(self, rules_path=".../data/policy_rules.json"): ...
        def classify(self, referral: dict) -> Decision: ...

Things to get right (see data/authority-policy.md, especially section 6):

1. Classify on substance, not just the label. A referral's requested_action
   field can say something perfectly permitted ("draft triage note") while
   its summary describes something that isn't (an award reinstatement).
   Check both fields.

2. Fail safe. Policy 6.1: "Where it is unclear whether an action falls
   within section 3, it is to be treated as though it does." A referral
   that matches no restricted trigger AND doesn't clearly match a
   recognised safe pattern should escalate, not proceed.

3. Don't assume exactly one referral in the queue is out-of-authority —
   the data pack's own README warns against that assumption. Whatever
   matching approach you pick, run it against every referral in
   data/referral-queue.json and see what actually flags before deciding
   the logic is right.

4. Keep this module ignorant of *how many* rules exist or what their IDs
   are — it should just iterate whatever policy_rules.json contains.
"""

# TODO: implement Decision and PolicyEngine
