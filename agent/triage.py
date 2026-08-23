"""
Triage note drafting & escalation records.

Two outputs, both non-mutating (policy 2.4: "A drafted note is a proposal.
It has no effect on the case until a caseworker adopts it."). Neither
function here performs or prepares the restricted action itself (policy
4.1) -- they only ever describe the situation and the decision.
"""
import json
import os
from datetime import datetime, timezone


def _age(dob_str, as_of="2026-03-17"):
    """Referrals in this data pack all arrived 2026-03-17; age is computed
    relative to that date rather than "today" so notes stay correct
    however long after the fact this module runs."""
    try:
        dob = datetime.strptime(dob_str, "%Y-%m-%d")
        ref = datetime.strptime(as_of, "%Y-%m-%d")
        years = ref.year - dob.year - ((ref.month, ref.day) < (dob.month, dob.day))
        return years
    except (ValueError, TypeError):
        return None


def draft_triage_note(referral, resident, out_dir):
    """
    For a referral classified "autonomous" (Module 3). Reads like
    something a caseworker can act on directly: the situation, the
    requested action, relevant household/case-history context pulled from
    the resident record (Module 2's output), and an explicit "this is a
    proposal" line.

    Returns the path written.
    """
    household = resident.get("household", [])
    events = sorted(resident.get("events", []), key=lambda e: e.get("date", ""), reverse=True)
    recent_events = events[:3]

    lines = [
        "TRIAGE NOTE (DRAFT -- proposal only, not yet adopted)",
        f"Referral: {referral['referral_id']}  |  Resident: {referral['resident_ref']}",
        f"Received: {referral['received_at']}  |  Source: {referral['source']}  |  "
        f"Urgency (as assessed by referrer): {referral['urgency']}",
        "",
        "Situation:",
        f"  {referral['summary']}",
        f"  Requested action: {referral['requested_action']}",
        "",
        "Case context (from resident history):",
        f"  Status: {resident.get('status')}  |  Benefit: {resident.get('benefit_code')}  |  "
        f"District: {resident.get('district')}  |  Current award: {resident.get('award_monthly')}/mo",
        f"  Household ({len(household)}):",
    ]
    for m in household:
        age = _age(m.get("date_of_birth", ""))
        age_str = f", age {age}" if age is not None else ""
        lines.append(f"    - {m['name']} ({m['relationship']}{age_str})")
    lines.append("  Recent case events:")
    for e in recent_events:
        lines.append(f"    - {e['date']}: {e['type']} -- {e['detail']}")
    lines += [
        "",
        "Recommendation:",
        f"  Within agent authority. Proceed with: {referral['requested_action']}.",
        "  This note is a proposal; a caseworker must review and adopt it before",
        "  anything in the resident's case changes.",
    ]

    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"{referral['referral_id']}.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return path


def write_escalation(referral, resident, decision, out_dir):
    """
    For a referral classified "requires_approval" (Module 3). Policy 4.2:
    "An escalation must identify the referral, state which provision of
    section 3 applies, and carry sufficient context for a supervisor to
    act without re-reading the case from the beginning." decision is a
    policy_engine.Decision (or anything exposing .to_dict() with
    matched_rules + reason).

    Returns the path written.
    """
    matched_rules = decision.to_dict()["matched_rules"] if hasattr(decision, "to_dict") else decision["matched_rules"]
    reason = decision.reason if hasattr(decision, "reason") else decision["reason"]

    events = sorted(resident.get("events", []), key=lambda e: e.get("date", ""), reverse=True)

    record = {
        "referral_id": referral["referral_id"],
        "resident_ref": referral["resident_ref"],
        "received_at": referral["received_at"],
        "source": referral["source"],
        "summary": referral["summary"],
        "requested_action": referral["requested_action"],
        "urgency_as_reported": referral["urgency"],
        "policy_ref": "ACA-2026/1",
        "matched_rules": matched_rules,
        "reason": reason,
        "agent_action_taken": "None. Referral escalated per policy 4.1; no restricted "
                               "action was performed or prepared.",
        "resident_context": {
            "status": resident.get("status"),
            "benefit_code": resident.get("benefit_code"),
            "district": resident.get("district"),
            "award_monthly": resident.get("award_monthly"),
            "household_size": len(resident.get("household", [])),
            "most_recent_event": events[0] if events else None,
        },
        "status": "AWAITING_SUPERVISOR_APPROVAL",
        "escalated_at": datetime.now(timezone.utc).isoformat(),
    }
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"{referral['referral_id']}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(record, f, indent=2)
    return path
