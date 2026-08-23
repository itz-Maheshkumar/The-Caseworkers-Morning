"""
MODULE 2 — History client.

A thin client for the mock Resident History API in services/history_service.py.
That service exposes GET-only routes — deliberately: there is no
create/update/delete endpoint anywhere in it. Keep it that way in mind while
building this client; it's the first, structural layer of the authority
guardrail (nothing in this codebase can be given a way to mutate a
resident's record, because nothing it talks to accepts a mutation).

Run the service first:
    python3 services/history_service.py --port 8083

Endpoints to wrap:
    GET /residents/<ref>            -> full record (status, benefit_code,
                                        district, award_monthly, household, events)
    GET /residents/<ref>/household  -> household composition only
    GET /residents/<ref>/events     -> case events only
    GET /health                     -> {"status": "ok", "records": <n>}

Contract for this module:

    class HistoryClient:
        def __init__(self, base_url="http://127.0.0.1:8083"): ...
        def get_resident(self, resident_ref: str) -> dict: ...
        def get_household(self, resident_ref: str) -> dict: ...
        def get_events(self, resident_ref: str) -> dict: ...
        def health(self) -> dict: ...

Notes:
- Use the standard library only (urllib.request) — matches the mock
  service's own "Python 3 standard library only" constraint from README.md.
- A 404 from the service comes back as a JSON body like
  {"error": "not_found", "resident_ref": "..."} with an HTTP error status —
  decide here whether callers see the raised HTTPError or a parsed dict;
  policy_engine.py / run_agent.py should not need to know the difference.
"""

# TODO: implement HistoryClient
