"""
Triage note drafting, escalation records, and hand-off records.

Three outputs, all non-mutating (policy 2.4: "A drafted note is a
proposal. It has no effect on the case until a caseworker adopts it.").
None of the functions here performs or prepares a restricted action, and
write_handoff() doesn't even produce a note -- see its docstring.
"""
import json
import os
from datetime import datetime, timezone

from dates import age_years as _age


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


def _resident_context(resident):
    """Shared by write_escalation() and write_handoff(). resident may be
    None -- a history fetch can fail independently of what the text-based
    classifier decides, since classify() never needed resident data in the
    first place. Returns a context dict with everything null if so, rather
    than requiring every caller to guard against a missing resident."""
    if resident is None:
        return {
            "status": None, "benefit_code": None, "district": None,
            "award_monthly": None, "household_size": None, "most_recent_event": None,
            "note": "Resident history could not be retrieved.",
        }
    events = sorted(resident.get("events", []), key=lambda e: e.get("date", ""), reverse=True)
    return {
        "status": resident.get("status"),
        "benefit_code": resident.get("benefit_code"),
        "district": resident.get("district"),
        "award_monthly": resident.get("award_monthly"),
        "household_size": len(resident.get("household", [])),
        "most_recent_event": events[0] if events else None,
    }


def write_escalation(referral, resident, decision, out_dir):
    """
    For a referral classified "requires_approval" (Module 3, Section 3.1-3.8
    -- text-based restrictions). Policy 4.2: "An escalation must identify
    the referral, state which provision of section 3 applies, and carry
    sufficient context for a supervisor to act without re-reading the case
    from the beginning." decision is a policy_engine.Decision (or anything
    exposing .to_dict() with matched_rules + reason).

    resident may be None if the history fetch failed -- classify() only
    needs the referral's own text, so a failed fetch doesn't prevent this
    branch being reached; resident_context is simply filled with nulls.

    Returns the path written.
    """
    matched_rules = decision.to_dict()["matched_rules"] if hasattr(decision, "to_dict") else decision["matched_rules"]
    reason = decision.reason if hasattr(decision, "reason") else decision["reason"]

    record = {
        "record_type": "escalation",
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
        "resident_context": _resident_context(resident),
        "status": "AWAITING_SUPERVISOR_APPROVAL",
        "escalated_at": datetime.now(timezone.utc).isoformat(),
    }
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"{referral['referral_id']}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(record, f, indent=2)
    return path


def write_handoff(referral, resident, decision, out_dir):
    """
    For a referral where policy_engine.check_household_restriction()
    (Amendment ACA-2026/2, clause 3.9) returned "handoff_required" --
    either because the household includes a minor, or because household
    composition couldn't be established at all (clause 5.2 -- treated the
    same way).

    This is deliberately NOT write_escalation() reused with a different
    label. Clause 3.3 requires a hand-off be distinguishable from an
    escalation: an escalation means "the Department must decide whether
    this may happen at all"; a hand-off means "this is ordinary casework a
    person must do." Three things make that distinction real rather than
    cosmetic: a different status string, a different record_type, and
    (enforced by the caller, run_agent.py) a different output directory --
    so nothing needs to parse a field carefully to tell the two apart.

    No triage note is produced anywhere in this function, and none should
    be -- clause 2.2 prohibits producing the draft itself, not merely its
    adoption. What gets written instead is whatever context was already
    established (resident_context; None-safe, same as write_escalation),
    so the caseworker doesn't have to repeat work already done (3.2/4.2).

    Returns the path written.
    """
    matched_rules = decision.to_dict()["matched_rules"] if hasattr(decision, "to_dict") else decision["matched_rules"]
    reason = decision.reason if hasattr(decision, "reason") else decision["reason"]

    record = {
        "record_type": "hand_off",
        "referral_id": referral["referral_id"],
        "resident_ref": referral["resident_ref"],
        "received_at": referral["received_at"],
        "source": referral["source"],
        "summary": referral["summary"],
        "requested_action": referral["requested_action"],
        "urgency_as_reported": referral["urgency"],
        "policy_ref": "ACA-2026/1 (amended by ACA-2026/2)",
        "matched_rules": matched_rules,
        "reason": reason,
        "agent_action_taken": "None. No triage note was drafted or prepared -- amendment "
                               "ACA-2026/2 clause 3.9 prohibits producing the draft itself, "
                               "not merely its adoption. This is a hand-off of ordinary "
                               "casework, not an escalation: see clause 3.3.",
        "resident_context": _resident_context(resident),
        "status": "HANDED_OFF_TO_CASEWORKER",
        "handed_off_at": datetime.now(timezone.utc).isoformat(),
    }
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"{referral['referral_id']}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(record, f, indent=2)
    return path
