"""
Core agent loop implementing: Goal -> Understand -> Plan -> Execute ->
Observe -> Adapt -> Verify -> Complete.

Run:
    python agent.py "Find the latest invoice from Acme Corp, extract the
    amount and due date, enter it into our internal system, and tell me
    once it is done."
"""

import sys
import json
import re

import mock_env
import planner

MAX_STEPS = 10


def extract_company_name(task_text: str) -> str:
    """
    Very small natural-language parse to pull the company name out of the
    task so the memory has something to start from. This is intentionally
    simple (see README limitations) - a production system would hand this
    to the LLM planner directly instead of a regex.
    """
    m = re.search(r"from\s+([A-Za-z0-9 .&]+?)(?:,|\.|$)", task_text)
    return m.group(1).strip() if m else task_text.strip()


def run_task(task_text: str, auto_clarify_answer: str | None = None):
    memory = {"company_name": extract_company_name(task_text)}
    history = []
    log = []

    def record(step):
        log.append(step)
        print(json.dumps(step, indent=2))

    for step_num in range(1, MAX_STEPS + 1):
        decision = planner.plan_next_action(task_text, memory, history, mock_env.TOOL_SCHEMAS)

        if decision["action"] == "done":
            record({"step": step_num, "type": "complete", "summary": decision["summary"]})
            return {"status": "success", "summary": decision["summary"], "trace": log}

        if decision["action"] == "ask_human":
            record({"step": step_num, "type": "ask_human", "question": decision["question"]})
            if auto_clarify_answer is None:
                # pause for a real human in an interactive run
                answer = input(f"[agent needs input] {decision['question']} > ")
            else:
                answer = auto_clarify_answer
            memory["asked_clarification"] = True
            memory["company_name"] = answer
            # retry the search with the corrected name: drop the prior failed
            # search_invoices attempt so the planner re-triggers it, rather
            # than treating the search step as already "done".
            history[:] = [h for h in history if h.get("tool") != "search_invoices"]
            memory.pop("search_matches", None)
            memory.pop("company_key", None)
            record({"step": step_num, "type": "human_response", "answer": answer})
            continue

        # action == call_tool
        tool_name = decision["tool"]
        args = decision.get("args", {})
        try:
            result = getattr(mock_env, tool_name)(**args)
            observation = {"tool": tool_name, "args": args, "status": "ok", "result": result}

            # update memory based on which tool ran (lets the loop progress)
            if tool_name == "search_invoices":
                memory["search_matches"] = result
                memory["company_key"] = result[0][0] if result else None
            elif tool_name == "get_invoice_details":
                memory["amount"] = result["amount"]
                memory["due_date"] = result["due_date"]
            elif tool_name == "enter_into_internal_system":
                memory["last_write_failed"] = False
            elif tool_name == "query_internal_system":
                memory["verified"] = (
                    result is not None
                    and result.get("amount") == memory.get("amount")
                    and result.get("due_date") == memory.get("due_date")
                )

        except mock_env.ToolError as e:
            observation = {"tool": tool_name, "args": args, "status": "failed", "error": str(e)}
            if tool_name == "enter_into_internal_system":
                memory["last_write_failed"] = True

        history.append(observation)
        record({"step": step_num, "type": "action", **observation})

    record({"step": MAX_STEPS, "type": "giving_up",
            "summary": "Reached max steps without completing the task."})
    return {"status": "incomplete", "trace": log}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python agent.py \"<natural language task>\"")
        sys.exit(1)
    task = sys.argv[1]
    result = run_task(task)
    print("\n=== FINAL RESULT ===")
    print(json.dumps({k: v for k, v in result.items() if k != "trace"}, indent=2))
