"""Tool safety tests — the calculator must never execute arbitrary code."""
from __future__ import annotations

from app.runtime.tools import available_tools, calculator, get_langchain_tools


def test_calculator_correct_math():
    assert calculator("2 + 3 * 4") == "14"
    assert calculator("(2 + 3) ** 2") == "25"


def test_calculator_rejects_code_execution():
    # These must be refused (returned as an error string), not evaluated.
    for malicious in ["__import__('os').system('echo hi')", "open('x')", "1; 2"]:
        out = calculator(malicious)
        assert "error" in out.lower()


def test_unknown_tool_is_ignored_gracefully():
    # Referencing a removed tool must not crash agent construction.
    tools = get_langchain_tools(["calculator", "does_not_exist"])
    assert len(tools) == 1


def test_tool_catalog_shape():
    for spec in available_tools():
        assert "name" in spec and "description" in spec
