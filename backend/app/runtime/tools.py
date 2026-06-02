"""Real tools agents can execute.

These are *real* side-effecting capabilities (not stubs): live web search, HTTP
fetch, a safe arithmetic evaluator, and a clock. Each tool is a plain callable
plus a small spec so we can (a) bind them to Gemini for function-calling and
(b) render the available toolbox in the UI.

Adding a new tool = write a function + register it in `TOOL_REGISTRY`. That is
the entire extension contract (documented in the README).
"""
from __future__ import annotations

import ast
import operator
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable

import httpx


# ── Individual tool implementations ─────────────────────────────────
def web_search(query: str, max_results: int = 5) -> str:
    """Search the public web (DuckDuckGo) and return top result snippets.

    DuckDuckGo occasionally rate-limits or blocks a given network/IP. To stay
    useful during a live demo we (a) retry across DDG backends with a short
    pause, and (b) return an explicit, actionable message when search is
    unavailable so the calling agent degrades gracefully (answers from its own
    knowledge) instead of looping on empty results.
    """
    import time

    try:
        from ddgs import DDGS

        results: list[dict] = []
        # Try the default backend, then explicit alternates.
        for attempt, backend in enumerate(("auto", "html", "lite")):
            try:
                with DDGS() as ddgs:
                    results = list(
                        ddgs.text(query, max_results=max_results, backend=backend)
                    )
                if results:
                    break
            except Exception:  # noqa: BLE001 — try the next backend
                pass
            if attempt < 2:
                time.sleep(1.0)  # brief pause before retrying a different backend

        if not results:
            return (
                f"[web_search unavailable for {query!r} — search backend returned "
                "no results (possibly rate-limited). Answer from your own knowledge "
                "and clearly note that live web results were not available.]"
            )

        lines = [
            f"{i + 1}. {r.get('title', '')}\n   {r.get('body', '')}\n   {r.get('href', '')}"
            for i, r in enumerate(results)
        ]
        return "\n".join(lines)
    except Exception as exc:  # noqa: BLE001 — tools must fail soft
        return (
            f"[web_search error: {exc}. Answer from your own knowledge and note "
            "that live web results were not available.]"
        )


def http_get(url: str) -> str:
    """Fetch a URL and return the first ~4000 chars of the text body."""
    try:
        resp = httpx.get(url, timeout=15, follow_redirects=True)
        resp.raise_for_status()
        text = resp.text
        return text[:4000] + ("…[truncated]" if len(text) > 4000 else "")
    except Exception as exc:  # noqa: BLE001
        return f"http_get error: {exc}"


# A whitelist of arithmetic operators — we never use eval().
_ALLOWED_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def _safe_eval(node: ast.AST) -> float:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED_OPS:
        return _ALLOWED_OPS[type(node.op)](_safe_eval(node.left), _safe_eval(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _ALLOWED_OPS:
        return _ALLOWED_OPS[type(node.op)](_safe_eval(node.operand))
    raise ValueError("unsupported expression")


def calculator(expression: str) -> str:
    """Safely evaluate an arithmetic expression, e.g. '2 * (3 + 4) ** 2'."""
    try:
        tree = ast.parse(expression, mode="eval")
        return str(_safe_eval(tree.body))
    except Exception as exc:  # noqa: BLE001
        return f"calculator error: {exc}"


def current_time() -> str:
    """Return the current UTC date and time (ISO-8601)."""
    return datetime.now(timezone.utc).isoformat()


# ── Registry ────────────────────────────────────────────────────────
@dataclass
class ToolSpec:
    name: str
    func: Callable[..., str]
    description: str


TOOL_REGISTRY: dict[str, ToolSpec] = {
    "web_search": ToolSpec(
        "web_search", web_search,
        "Search the public web for current information. Args: query (str).",
    ),
    "http_get": ToolSpec(
        "http_get", http_get,
        "Fetch the text content of a URL. Args: url (str).",
    ),
    "calculator": ToolSpec(
        "calculator", calculator,
        "Evaluate an arithmetic expression. Args: expression (str).",
    ),
    "current_time": ToolSpec(
        "current_time", current_time,
        "Get the current UTC date and time. No args.",
    ),
}


def available_tools() -> list[dict[str, str]]:
    """List tool specs for the UI / API."""
    return [{"name": s.name, "description": s.description} for s in TOOL_REGISTRY.values()]


def get_langchain_tools(names: list[str]) -> list:
    """Build LangChain StructuredTools for the given tool names.

    Unknown names are ignored (an agent referencing a removed tool degrades
    gracefully rather than crashing the run).
    """
    from langchain_core.tools import StructuredTool

    tools = []
    for name in names:
        spec = TOOL_REGISTRY.get(name)
        if spec is None:
            continue
        tools.append(
            StructuredTool.from_function(
                func=spec.func, name=spec.name, description=spec.description
            )
        )
    return tools
