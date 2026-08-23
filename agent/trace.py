"""
MODULE 4 — Execution trace.

Policy 5.1/5.2: "Every action taken by an assistant must be recorded in a
form that allows a supervisor to reconstruct, after the fact, what was
done, in what order, on what information, and what was declined. A record
which shows only the assistant's output, and not the steps that produced
it, does not satisfy 5.1." This module is how the floor requirement "a
visible execution trace" gets met — it has to log the steps, not just the
final drafted note / escalation.

Contract:

    class Trace:
        def __init__(self, path): ...       # opens/creates the trace file
        def log(self, event_type: str, **fields) -> None: ...
        def close(self) -> None: ...

Suggested event types to emit from run_agent.py as it works through the
queue: run_started, referral_read, history_retrieved (or
history_fetch_failed), policy_decision, triage_note_drafted, escalated,
run_finished.

Format: write structured entries (e.g. one JSON object per line —
"JSON Lines" — to output/trace.jsonl) AND print a readable line to stdout
as each event happens, so the trace is both greppable/parseable and
readable live while the agent runs. Include a timestamp on every entry.
"""

# TODO: implement Trace
