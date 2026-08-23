"""
Execution trace.

Policy 5.1/5.2: "Every action taken by an assistant must be recorded in a
form that allows a supervisor to reconstruct, after the fact, what was
done, in what order, on what information, and what was declined. A record
which shows only the assistant's output, and not the steps that produced
it, does not satisfy 5.1."

Every step run_agent.py takes gets appended here, in order, as one JSON
object per line (JSON Lines) -- machine-parseable, and also trivial to
read/grep by a human, which is what "visible execution trace" in the
brief's floor requirement means in practice.
"""
import json
import os
from datetime import datetime, timezone


class Trace:
    def __init__(self, path):
        self.path = path
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self._fh = open(path, "w", encoding="utf-8")

    def log(self, event_type, **fields):
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "event": event_type,
            **fields,
        }
        self._fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
        self._fh.flush()  # readable on disk immediately, even if the run crashes later
        print(f"[{entry['ts']}] {event_type:22s} {_summarise(fields)}")
        return entry

    def close(self):
        self._fh.close()

    # Support "with Trace(path) as t:" so run_agent.py can guarantee close()
    # even if something raises mid-run.
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()
        return False


def _summarise(fields):
    """What gets echoed to stdout alongside each event -- just the fields
    that make a line scannable live; the full entry always goes to the file."""
    parts = []
    for k in ("referral_id", "resident_ref", "status", "rule_ids", "reason",
              "autonomous", "escalated", "failed", "referral_count"):
        if k in fields:
            parts.append(f"{k}={fields[k]}")
    return " ".join(parts)
