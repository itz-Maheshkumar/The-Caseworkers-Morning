"""
Policy engine.

Reads data/policy_rules.json and decides, for a given referral, whether it
falls inside the agent's own authority (Section 2 of ACA-2026/1) or requires
supervisor approval (Section 3).

Nothing about the policy's content is hard-coded here. If ACA-2026/1 is
revised (including the "day two" change mentioned in the brief), only
data/policy_rules.json needs to change -- this file's logic does not.

Amendment ACA-2026/2 (clause 3.9) added a second, independent kind of
restriction: whether a household includes a minor. That's evaluated from
resident data, not referral text, which is why it's a separate method,
check_household_restriction(), rather than folded into classify(). The two
are deliberately kept apart: classify()'s contract (referral in, Decision
out, no resident data involved) is exactly what Modules 3 and 8 were built
and tested against, and changing its signature would be exactly the kind
of code-shaped change day two was warned might come.
"""
import json
import os

from dates import age_years

_HERE = os.path.dirname(os.path.abspath(__file__))
_RULES_PATH = os.path.join(_HERE, "..", "data", "policy_rules.json")


class Decision:
    def __init__(self, status, matched_rules, reason):
        self.status = status                # "autonomous" | "requires_approval"
                                             # (classify()) or "clear" | "handoff_required"
                                             # (check_household_restriction())
        self.matched_rules = matched_rules  # list of rule dicts from policy_rules.json
        self.reason = reason                # human-readable -- goes into the trace
                                             # and into escalation records verbatim

    def to_dict(self):
        return {
            "status": self.status,
            "matched_rules": [
                {"id": r["id"], "label": r.get("label"), "description": r["description"]}
                for r in self.matched_rules
            ],
            "reason": self.reason,
        }

    def __repr__(self):
        ids = ",".join(r["id"] for r in self.matched_rules) or "-"
        return f"Decision(status={self.status!r}, rules=[{ids}])"


class PolicyEngine:
    def __init__(self, rules_path=_RULES_PATH):
        with open(rules_path, encoding="utf-8") as f:
            self.rules = json.load(f)

    def classify(self, referral):
        """
        Classify a referral against the restricted-action triggers in
        policy_rules.json.

        A referral is judged on requested_action AND summary together --
        the substance of the case, not just the label the referrer gave
        it. (See RF-2026-0422 in the data pack: requested_action reads
        "Draft triage note for supervisor" -- itself permitted -- while
        the summary describes an award reinstatement, which isn't.)
        """
        text = f"{referral.get('requested_action', '')} {referral.get('summary', '')}".lower()

        matched = []
        for rule in self.rules["restricted_actions"]:
            if any(trigger in text for trigger in rule["triggers"]):
                matched.append(rule)

        if matched:
            ids = ", ".join(r["id"] for r in matched)
            return Decision(
                "requires_approval",
                matched,
                f"Requested action/summary matches restricted action(s) {ids} "
                f"under policy {self.rules['policy_ref']}."
            )

        # No restricted trigger matched. Does it match a recognised safe
        # pattern, or is it genuinely unclear? Per policy 6.1, "unclear"
        # defaults to requires_approval rather than to autonomous.
        safe_patterns = self.rules.get("recognised_safe_actions", [])
        requested = referral.get("requested_action", "").lower()
        if any(pattern in requested for pattern in safe_patterns):
            return Decision(
                "autonomous",
                [],
                "Requested action matches a recognised autonomous pattern "
                "(Section 2) and triggers no restricted-action pattern (Section 3)."
            )

        return Decision(
            self.rules["default_when_unclear"],
            [],
            self.rules["default_reason"] + " (No recognised safe pattern matched either.)"
        )

    def check_household_restriction(self, resident):
        """
        Amendment ACA-2026/2, clause 3.9: drafting a triage note is not
        permitted for a referral concerning a household that includes
        anyone under 18. Evaluated purely from the resident's household
        composition -- pass the dict HistoryClient.get_resident() returns,
        or None if history could not be fetched at all.

        Returns a Decision: status "handoff_required" (do not draft; hand
        off instead -- see triage.write_handoff()) or "clear" (3.9 doesn't
        apply; the caller may proceed to draft as normal).

        Per clause 5.2, an unknown household composition (resident is None,
        or has no household data) is treated as 3.9 applying -- the same
        fail-safe shape as classify()'s default_when_unclear for 6.1.
        """
        household_rules = self.rules.get("household_restrictions", [])
        if not household_rules:
            # No such rule defined in policy_rules.json -- nothing to check.
            return Decision("clear", [], "No household-based restrictions are defined.")

        rule = household_rules[0]  # currently only 3.9

        if resident is None or "household" not in resident:
            return Decision(
                "handoff_required",
                [rule],
                f"Household composition could not be established. Per "
                f"{rule['on_composition_unknown_reason']}"
            )

        threshold = rule.get("age_threshold_years", 18)
        minors = [
            m for m in resident["household"]
            if (a := age_years(m.get("date_of_birth", ""))) is not None and a < threshold
        ]

        if minors:
            names = ", ".join(f"{m['name']} (age {age_years(m['date_of_birth'])})" for m in minors)
            return Decision(
                "handoff_required",
                [rule],
                f"Household includes person(s) under {threshold}: {names}. "
                f"Per amendment {rule['amendment_ref']} clause {rule['id']}, no "
                f"triage note may be drafted for this referral."
            )

        return Decision(
            "clear",
            [],
            f"Household composition established; no member under {threshold}. "
            f"Rule {rule['id']} does not apply."
        )
