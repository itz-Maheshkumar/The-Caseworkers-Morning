"""
Shared date helper.

Referrals in this data pack all arrived 2026-03-17. Age-based
determinations -- a triage note's household ages (triage.py), and
Amendment ACA-2026/2's minor-in-household check (policy_engine.py) -- are
computed relative to that date rather than whatever date this code
happens to run on, so the two places that need "how old is this person"
never disagree with each other.
"""
from datetime import datetime

REFERRAL_BATCH_DATE = "2026-03-17"


def age_years(dob_str, as_of=REFERRAL_BATCH_DATE):
    try:
        dob = datetime.strptime(dob_str, "%Y-%m-%d")
        ref = datetime.strptime(as_of, "%Y-%m-%d")
        return ref.year - dob.year - ((ref.month, ref.day) < (dob.month, dob.day))
    except (ValueError, TypeError):
        return None
