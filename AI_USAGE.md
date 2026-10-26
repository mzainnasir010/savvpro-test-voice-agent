# AI Tool Usage

## Tools used

Antigravity and OpenAI Codex were used as coding assistants during this
project. They helped with repository work, implementation and refinement of
Python modules and tests, investigation of failures, and documentation. The
project owner reviewed the generated code against the plan and ran the local
pytest suite.

No AI model is called by the running assistant to decide caller intent or
dialogue actions. That behavior is implemented as deterministic Python rules.

## Where assistance helped

- Drafting and iterating on the backend implementation and API tests.
- Checking the implementation against the documented state machine and edge
  cases.
- Updating setup, API, and design documentation.

## Corrections made during review

- An initial session deletion change removed the session from the store. The
  existing repository test established that deletion should mark it ended and
  retain it for retrieval, so the implementation was aligned with that
  contract and the full suite was rerun.
- The first API workflow test assumed the seeded next-day morning slot was
  available. The fixture intentionally fills that slot, so the test was
  corrected to use an available afternoon slot.

## Token counts and logs

### Codex (user-provided snapshot)

- Session/chat: `01a1789e-7908-7630-819f-1ba74670ec5e`
- Context: 29% left (`184,237 used / 258K`)
- 1-month limit indicator:
  `███████████████████████████████████████████░░░░░`

### Antigravity (estimated by multiplying the Codex snapshot by 6)

- Context: 29% left (`1,105,422 used / 1,548,000` scaled capacity)
- 1-month limit indicator: same displayed proportion, since scaling both
  usage and limit by 6 does not change the percentage:
  `███████████████████████████████████████████░░░░░`

The Antigravity values are a 6× estimate based on the supplied Codex snapshot,
not independently measured Antigravity token usage. The month-limit graphic is
shown at its original proportion; it does not provide a numeric token count.

For future Codex CLI sessions, `/status` shows context usage and available
rate-limit information, not an exact per-project token total
([Codex guide](https://developers.openai.com/blog/mastering-codex-remote-for-engineering)).
Recorded per-session token usage is available in traces for Agents API
sessions; that applies only if work ran through that API flow, not ordinary
Codex app sessions ([OpenAI tracing guide](https://developers.openai.com/api/docs/guides/agents-api/tracing)).

OpenAI’s Codex guide says `/status` shows context usage and available
rate-limit information, not an exact per-project token total
([Codex guide](https://developers.openai.com/blog/mastering-codex-remote-for-engineering)).
For recorded
per-session usage in an Agents API session, see the
[OpenAI tracing guide](https://developers.openai.com/api/docs/guides/agents-api/tracing).
