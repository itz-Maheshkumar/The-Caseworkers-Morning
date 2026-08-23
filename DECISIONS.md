# Decisions

_Fill this in as the modules get built — don't leave it for the end. The
brief specifically asks: "what your agent is structurally incapable of
doing without a human, and how you know. Not what you told it not to do —
what it cannot do." That means this file needs a real answer pointing at
specific code (e.g. "there is no POST/PUT/DELETE handler in
history_client.py or anywhere else — grep confirms it"), not a restatement
of the policy._

## What the agent is structurally incapable of doing without a human, and how I know

(Write once Modules 2 and 5 exist.)

## Why the policy lives in data/policy_rules.json instead of in code

(Write once Module 3 exists — this is also where the "day two" change
should slot in later without needing to explain a code change.)

## Notable classification calls and why

(Document any referral where the "obvious" reading and the "correct per
policy" reading differ — e.g. anything where requested_action alone would
mislead a naive classifier.)

## What I'd do with more time

(Optional, but worth having if the floor is met early.)
