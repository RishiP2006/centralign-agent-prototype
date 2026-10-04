# Autonomous AI Task Worker (prototype)

A minimal agent that takes a natural-language task, plans and executes a
sequence of actions against a mock company environment (a fake invoice
portal + a fake internal system), recovers from a failed/ambiguous lookup
by asking for clarification, verifies its own work, and reports a summary.

Example task:
> "Find the latest invoice from Acme Corp, extract the amount and due date,
> enter it into our internal system, and tell me once it is done."

## Setup & Run

```bash
pip install -r requirements.txt   # only needed for LLM planning mode, see below
python agent.py "Find the latest invoice from Acme Corp, extract the amount and due date, enter it into our internal system, and tell me once it is done."
```

To exercise the failure-recovery path (company not in the mock DB), try:
```bash
python agent.py "Find the latest invoice from Initech Holdings, extract the amount and due date, enter it into our internal system, and tell me once it is done."
```
The agent will report it can't find a match and ask a clarifying question
on the terminal; answering `Initrode` lets it retry and complete the task.

**Optional LLM planning mode:** set `ANTHROPIC_API_KEY` in your environment
before running, and the planner will use Claude to decide each next action
instead of the rule-based fallback (see Architecture below).

## Architecture

The loop follows `Goal -> Understand -> Plan -> Execute -> Observe -> Adapt
-> Verify -> Complete`:

- **`mock_env.py`** — the simulated external world: an invoice lookup
  ("portal") and an internal record store, exposed as a small set of tools
  with declared schemas. One tool (`enter_into_internal_system`) has a 10%
  injected failure rate to exercise retry handling.
- **`planner.py`** — given the goal, current memory, and action history,
  decides the single next action: call a tool, ask the human a clarifying
  question, or declare the task done. Two interchangeable implementations:
  - **LLM mode** (if `ANTHROPIC_API_KEY` is set): Claude receives the goal,
    memory, history, and tool schemas, and returns the next action as JSON.
  - **Rule-based fallback** (default, no API key required): a deterministic
    state machine covering the same task family, so the prototype runs
    out-of-the-box.
- **`agent.py`** — the control loop: calls the planner, executes the chosen
  tool, updates memory with whatever was discovered (invoice amount, due
  date, etc.), logs every step as structured JSON (the "evidence" of what
  happened), and loops until the planner reports `done` or a max step count
  is hit as a safety bound.

## Key design decisions

- **Mock environment instead of real browser/API access** — per the brief's
  guidance to avoid real credentials/third-party systems, and because a
  narrow, genuinely-working system was prioritized over a broad one that
  mostly simulates success.
- **Dual planner (LLM + rule-based fallback)** — makes the prototype
  demonstrably reasoning-driven when an API key is available, while staying
  runnable (and gradeable) without one.
- **Explicit memory dict** — rather than relying on an LLM's own context
  window, discovered facts (amount, due date, matched company key) are
  written to a plain Python dict so the state the agent is reasoning over is
  fully inspectable at every step.
- **Structured JSON logging of every step** — serves as the "evidence of
  completion" the brief asks for, and makes the agent's decisions auditable.

## What's genuinely autonomous

- Deciding *which* tool to call next based on what's been discovered so far
  (not a hardcoded fixed sequence — e.g. if a search returns no match, the
  next action branches to clarification instead of continuing blindly).
- Detecting a failed/ambiguous search and choosing to ask for human input
  rather than guessing.
- Re-attempting the search once new information (a corrected company name)
  is available.
- Verifying the write against the internal system's own record rather than
  trusting the write call's return value alone, and retrying the write if
  verification fails.

## What's currently hardcoded / manually configured

- The mock invoice database and internal system are in-memory Python dicts
  seeded with 3 example companies — not a real database.
- The rule-based planner fallback is scoped specifically to the
  invoice-lookup-and-entry task family; it would not generalize to an
  unrelated task without the LLM planning mode.
- The natural-language company-name extraction in `agent.py` uses a simple
  regex rather than an LLM call, to keep the prototype runnable without an
  API key end-to-end.
- The clarification step auto-continues via a CLI `input()` prompt — there's
  no persistent approval/notification system, just a synchronous pause.

## Known limitations

- Only one task family (invoice lookup → entry) is supported; the rule-based
  planner does not generalize to arbitrary tasks (the LLM planner mode is
  closer to general-purpose, but untested beyond this task type).
- No real browser or desktop automation — the "tools" are Python functions
  simulating what those actions would do.
- Retry logic is a single blind retry on write failure, not an exponential
  backoff or bounded retry budget.
- No persistence between runs (memory/history reset each execution).

## What I'd build next with more time

- Swap the mock tools for real ones (e.g. an actual browser-automation tool
  for a sandboxed test site) behind the same tool-schema interface, so the
  planner/loop logic doesn't need to change — testing the generalization
  claim directly.
- A proper bounded-retry/backoff policy and a clearer taxonomy of
  recoverable vs. non-recoverable tool failures.
- Persist state so a long-running task can be paused for human approval and
  resumed later rather than blocking synchronously on `input()`.
- Multi-task planning (a queue of goals) rather than one task per run.

## Assumptions

- "Latest invoice" is resolved by exact/fuzzy company-name match against the
  mock DB (there's only one invoice per company in the mock data, so
  recency isn't separately modeled).
- A human is available synchronously to answer a clarification question
  during the run (no async notification system was built).

## Models / frameworks / libraries used

- Python 3 standard library for the agent loop and mock environment.
- `anthropic` Python SDK (Claude) for the optional LLM planning mode.
- No agent framework (LangChain/CrewAI/etc.) — the loop was hand-written to
  keep the architecture fully transparent and easy to explain/modify.
