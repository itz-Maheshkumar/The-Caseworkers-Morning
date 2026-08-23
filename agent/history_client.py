"""
History client.

A thin client for the mock Resident History API (services/history_service.py).

Note what this client CANNOT do: the service only exposes GET endpoints.
There is no create/update/delete route anywhere in history_service.py.
That means no code path in this whole project -- however it is instructed --
is physically capable of writing to a resident's record. The approval gate
in approval_gate.py (Module 5) is a second, belt-and-braces control on top
of that, but this is the first one: the mutating capability simply doesn't
exist in the environment. See DECISIONS.md.
"""
import json
import urllib.request
import urllib.error


class HistoryClient:
    def __init__(self, base_url="http://127.0.0.1:8083"):
        self.base_url = base_url.rstrip("/")

    def _get(self, path):
        """
        GET-only, deliberately. There is no _post/_put/_delete here and
        there should never be one -- see the module docstring.
        """
        url = f"{self.base_url}{path}"
        try:
            with urllib.request.urlopen(url, timeout=5) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            # The service returns a JSON error body (e.g. {"error": "not_found", ...})
            # even on 404s. Surface that body as a normal dict rather than
            # forcing every caller to catch HTTPError -- policy_engine.py
            # and run_agent.py only need to check for an "error" key.
            return json.loads(e.read().decode("utf-8"))
        except urllib.error.URLError as e:
            return {"error": "unreachable", "detail": str(e.reason)}

    def get_resident(self, resident_ref):
        """Full record: status, benefit_code, district, award_monthly, household, events."""
        return self._get(f"/residents/{resident_ref}")

    def get_household(self, resident_ref):
        """{'resident_ref': ..., 'household': [...]}"""
        return self._get(f"/residents/{resident_ref}/household")

    def get_events(self, resident_ref):
        """{'resident_ref': ..., 'events': [...]}"""
        return self._get(f"/residents/{resident_ref}/events")

    def health(self):
        """{'status': 'ok', 'service': 'resident-history', 'records': <n>}"""
        return self._get("/health")
