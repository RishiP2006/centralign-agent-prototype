"""
Planner: decides the next action given the goal, memory, and history so far.

Two modes:
  1. LLM mode (used if ANTHROPIC_API_KEY is set) - the planner calls Claude
     with the tool schemas and current state, and the model decides the next
     action. This is the "real" reasoning/planning path.
  2. Fallback rule-based mode (used otherwise) - a deterministic state
     machine covering the invoice-entry task family, so the prototype still
     runs end-to-end without needing an API key during a demo.

This split is a deliberate, disclosed design decision (see README "Known
limitations" / "Assumptions") rather than something hidden.
"""

import json
import os

USE_LLM = bool(os.environ.get("ANTHROPIC_API_KEY"))

if USE_LLM:
    import anthropic
    _client = anthropic.Anthropic()


def _llm_plan(goal, memory, history, tool_schemas):
    system = (
        "You are the planning module of an autonomous task-execution agent. "
        "Given a GOAL, the agent's current MEMORY (facts discovered so far), "
        "the HISTORY of actions already taken and their observations, and the "
        "list of AVAILABLE_TOOLS, decide the single next action.\n\n"
        "Respond with JSON only, one of:\n"
        '  {"action": "call_tool", "tool": "<name>", "args": {...}}\n'
        '  {"action": "done", "summary": "<final summary for the user>"}\n'
        '  {"action": "ask_human", "question": "<clarifying question>"}\n'
    )
    user = json.dumps({
        "goal": goal,
        "memory": memory,
        "history": history,
        "available_tools": tool_schemas,
    })
    resp = _client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=500,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    text = resp.content[0].text.strip()
    # tolerate the model wrapping JSON in a code fence
    if text.startswith("```"):
        text = text.strip("`").split("\n", 1)[1]
    return json.loads(text)


def _rule_based_plan(goal, memory, history, tool_schemas):
    """
    Deterministic fallback covering: search -> (fuzzy retry / clarify) ->
    get details -> enter into system -> verify -> done.
    """
    done_tools = [h["tool"] for h in history if h.get("status") == "ok"]

    if "search_invoices" not in done_tools:
        return {"action": "call_tool", "tool": "search_invoices",
                "args": {"company_name": memory["company_name"]}}

    matches = memory.get("search_matches")
    if matches == []:
        if memory.get("asked_clarification"):
            return {"action": "done",
                    "summary": f"Could not find an invoice for '{memory['company_name']}' "
                                f"after searching and asking for clarification."}
        return {"action": "ask_human",
                "question": f"No invoice found for '{memory['company_name']}'. "
                             f"Did you mean one of our known accounts? Please confirm the exact name."}

    if "get_invoice_details" not in done_tools:
        return {"action": "call_tool", "tool": "get_invoice_details",
                "args": {"company_key": memory["company_key"]}}

    if "enter_into_internal_system" not in done_tools or memory.get("last_write_failed"):
        return {"action": "call_tool", "tool": "enter_into_internal_system",
                "args": {"company_key": memory["company_key"],
                         "amount": memory["amount"], "due_date": memory["due_date"]}}

    if "query_internal_system" not in done_tools:
        return {"action": "call_tool", "tool": "query_internal_system",
                "args": {"company_key": memory["company_key"]}}

    verified = memory.get("verified")
    if verified:
        return {"action": "done",
                "summary": f"Invoice {memory['company_key']} entered and verified: "
                            f"amount={memory['amount']}, due_date={memory['due_date']}."}
    return {"action": "call_tool", "tool": "enter_into_internal_system",
            "args": {"company_key": memory["company_key"],
                     "amount": memory["amount"], "due_date": memory["due_date"]}}


def plan_next_action(goal, memory, history, tool_schemas):
    if USE_LLM:
        return _llm_plan(goal, memory, history, tool_schemas)
    return _rule_based_plan(goal, memory, history, tool_schemas)
