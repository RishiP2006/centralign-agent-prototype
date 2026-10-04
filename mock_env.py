"""
Mock company environment: a fake invoice portal and a fake internal system.

This simulates the two external systems the agent needs to interact with,
so the prototype can be evaluated without real browser automation or
credentials, per the submission guidelines ("use sandbox/mock environments").
"""

import random
import time

# --- Fake "invoice portal" data -------------------------------------------------

_INVOICE_DB = {
    "acme corp": {"id": "INV-1001", "amount": 4500.00, "due_date": "2026-10-15"},
    "globex": {"id": "INV-1002", "amount": 12300.50, "due_date": "2026-10-20"},
    "initrode": {"id": "INV-1003", "amount": 980.25, "due_date": "2026-10-10"},
}

# fake "internal system" storage the agent writes into
_INTERNAL_SYSTEM = {}


class ToolError(Exception):
    """Raised when a tool call fails (simulated real-world failure)."""


def _simulate_latency():
    time.sleep(0.15)


def search_invoices(company_name: str):
    """
    Search the invoice portal for a company name. Returns a list of
    (company_key, record) matches. Does a case-insensitive substring/fuzzy
    match so near-misses in the task phrasing still resolve.
    """
    _simulate_latency()
    q = company_name.strip().lower()

    # exact match first
    if q in _INVOICE_DB:
        return [(q, _INVOICE_DB[q])]

    # fuzzy: substring either direction
    matches = [
        (key, rec) for key, rec in _INVOICE_DB.items()
        if q in key or key in q
    ]
    return matches


def get_invoice_details(company_key: str):
    _simulate_latency()
    if company_key not in _INVOICE_DB:
        raise ToolError(f"No invoice on file for '{company_key}'")
    return _INVOICE_DB[company_key]


def enter_into_internal_system(company_key: str, amount: float, due_date: str):
    """
    Writes the extracted invoice data into the mock internal system.
    Simulates an occasional transient failure to exercise the agent's
    retry logic (10% chance), per the brief's interest in reliability.
    """
    _simulate_latency()
    if random.random() < 0.10:
        raise ToolError("Internal system timeout while writing record")

    _INTERNAL_SYSTEM[company_key] = {"amount": amount, "due_date": due_date}
    return {"status": "written", "company_key": company_key}


def query_internal_system(company_key: str):
    """Used by the agent's verification step to confirm the write succeeded."""
    _simulate_latency()
    return _INTERNAL_SYSTEM.get(company_key)


# Tool schema registry the planner (LLM or rule-based) reasons over.
TOOL_SCHEMAS = [
    {
        "name": "search_invoices",
        "description": "Search the invoice portal by company name. Returns possible matches.",
        "parameters": {"company_name": "string"},
    },
    {
        "name": "get_invoice_details",
        "description": "Get amount and due date for a specific company_key returned by search_invoices.",
        "parameters": {"company_key": "string"},
    },
    {
        "name": "enter_into_internal_system",
        "description": "Write the invoice amount and due date into the internal system.",
        "parameters": {"company_key": "string", "amount": "number", "due_date": "string"},
    },
    {
        "name": "query_internal_system",
        "description": "Read back what was written for a company_key, used to verify the write.",
        "parameters": {"company_key": "string"},
    },
]
