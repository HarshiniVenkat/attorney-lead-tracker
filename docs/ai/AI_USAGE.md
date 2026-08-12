# How I used coding agents

This project was built with **Claude Code** (Opus) in a single session on
8 August 2026, 01:22–06:46 UTC — about five and a half hours from an empty
directory to a pushed repository. Twenty-four messages from me, roughly 1,100
tool calls from the agent.

The full conversation is in [`transcript.md`](./transcript.md), with the
unedited log in [`transcript.jsonl`](./transcript.jsonl). This file explains how
I worked, and points at the moments in that transcript worth reading.

---

## The one rule I set up front

My first message, before any requirements:

> Let's first decide on how we want the application to look like and interact.
> **Once I approve of the design, let's go ahead and make the code changes.**

That gate did most of the work. An agent asked to "build this" will produce
something plausible in ten minutes and you will spend two hours discovering what
it assumed. Making it defend a design first moves the disagreement to the point
where changing your mind costs a sentence instead of a refactor.

Roughly forty minutes went to design, and no code was written until the schema,
the API surface, the auth model, and the email strategy were settled.

## What I pushed back on

The design that came back was competent and slightly over-built. Four
interventions shaped what actually got made.

**"What resume file type are we uploading here?"** — the proposal said
"pdf/doc/docx" and moved on. Pinning it down produced the decisions that
mattered: reject legacy `.doc`, cap at 5 MB, and validate by **magic bytes**
rather than the extension or the declared `Content-Type`, because both are
attacker-controlled. Files are stored under generated keys, never the
user-supplied filename. None of that was in the design until the vague line was
questioned.

**"Why do we need `is_active` for attorney? I don't think that is needed."** —
I was wrong, and I changed my mind once the reason was concrete:
`leads.reached_out_by_id` is a foreign key into `users`, so deleting a departed
attorney either blocks on the constraint or nulls the column, and the audit
trail loses exactly the accountability record it exists to keep. `is_active`
means revoking access and destroying history aren't the same operation. It
stayed. Worth noting the agent had proposed it *without* that justification —
the argument only appeared when challenged, which is why challenging is worth
the time.

**"For a take home, a good working product is more important than one with
multiple features."** — the email design came with a retry loop, backoff, and
`SKIP LOCKED`. I cut all three. The `email_deliveries` outbox stayed, because it
does something visible: emails are written in the same transaction as the lead,
so a mail outage can't fail a submission or silently lose a notification, and
failures surface in the dashboard instead of a log. The schema keeps `attempts`
and `next_attempt_at` unused, so retry is a later addition rather than a
rewrite.

**"The document is such overkill."** — the first system-design document was a
reference manual. I had it cut to about a third: what the pieces are, how the
front end calls the back end, the endpoint table, and two flow diagrams. The
test I applied was whether a non-engineer could follow it.

## The most useful thing that went wrong

Midway through, I couldn't log in to the dashboard. The credentials were right;
the `users` table was empty.

The cause was in the agent's own test configuration. `conftest.py` used
`os.environ.setdefault("DATABASE_URL", ...)` to point the suite at a throwaway
`alma_test` database — but docker-compose already sets `DATABASE_URL` in the
container, so `setdefault` was a silent no-op. The suite had been running
against the real development database, and its `TRUNCATE`-between-tests fixture
deleted the seeded attorney account.

What I asked for was the fix to the cause, not a re-seed. Two changes went in:
unconditional assignment that derives `<name>_test` from whatever `DATABASE_URL`
holds, and a collection-time guard that refuses to run at all if the target
database name doesn't end in `_test`. Verified by counting rows either side of a
full run — 1 user before, 68 tests pass, 1 user after.

I'm including this deliberately. It's the clearest illustration of the working
relationship: the agent wrote the bug, the agent found and fixed it, and it
only got fixed properly because the instruction was "fix the cause" rather than
"make it work again." An agent will happily re-seed the database and report
success.

## What I'd take from this

The leverage was almost entirely in the design conversation and in refusing the
first answer. The agent is fast and thorough and will over-engineer if you let
it; it also justifies decisions well when asked, and sometimes the justification
is good enough to change your mind — `is_active` survived because the argument
for it was better than my objection to it.

The parts I'd trust least without review are exactly the parts that look most
finished: test configuration that appears to isolate itself but doesn't, and
documentation that's thorough enough that nobody notices it's the wrong shape
for its reader.
