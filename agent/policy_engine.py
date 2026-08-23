"""
Policy engine.

Reads data/policy_rules.json and decides, for a given referral, whether it
falls inside the agent's own authority (Section 2 of ACA-2026/1) or requires
supervisor approval (Section 3).

Nothing about the policy's content is hard-coded here. If ACA-2026/1 is
revised (including the "day two" change mentioned in the brief), only
data/policy_rules.json needs to change -- this file's logic does not.
"""
import json
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_RULES_PATH = os.path.join(_HERE, "..", "data", "policy_rules.json")


class Decision:
    def __init__(self, status, matched_rules, reason):
        self.status = status                # "autonomous" | "requires_approval"
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
