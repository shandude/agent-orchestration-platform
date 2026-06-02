"""Shared test fixtures.

We point the app at a throwaway SQLite file *before* importing any app module,
so the cached settings + engine bind to the test database. A `FakeLLM` lets us
exercise the full agent runtime (routing, feedback loops, message persistence)
deterministically and offline — no Gemini key or network needed.
"""
from __future__ import annotations

import os
import tempfile

# ── Configure the environment BEFORE importing the app ──────────────
_TEST_DB = os.path.join(tempfile.gettempdir(), "yuno_test.db")
if os.path.exists(_TEST_DB):
    os.remove(_TEST_DB)
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB}"
os.environ.setdefault("GOOGLE_API_KEY", "")  # default: LLM "disabled"
os.environ["TELEGRAM_BOT_TOKEN"] = ""
os.environ["MAX_GRAPH_ITERATIONS"] = "15"

import pytest  # noqa: E402
from langchain_core.messages import AIMessage, SystemMessage  # noqa: E402

from app.database import Base, SessionLocal, init_db  # noqa: E402

init_db()


@pytest.fixture(autouse=True)
def _clean_db():
    """Truncate all tables between tests for isolation."""
    init_db()
    yield
    with SessionLocal() as db:
        for table in reversed(Base.metadata.sorted_tables):
            db.execute(table.delete())
        db.commit()


class FakeLLM:
    """A stand-in chat model that returns scripted, role-aware responses.

    It inspects the SystemMessage to decide which agent is calling, so a single
    fake can drive a multi-agent workflow including a REVISE→APPROVED loop.
    """

    def __init__(self) -> None:
        self.calls: dict[str, int] = {}

    def bind_tools(self, tools):  # noqa: ANN001 — mimic LangChain API
        return self

    def _who(self, messages) -> str:
        for m in messages:
            if isinstance(m, SystemMessage):
                return m.content
        return ""

    async def ainvoke(self, messages):  # noqa: ANN001
        # engine._llm_route passes a raw string; default that branch.
        if isinstance(messages, str):
            return AIMessage(content="0", usage_metadata=_usage())

        system = self._who(messages)
        if "Editor" in system or "editor" in system:
            self.calls["editor"] = self.calls.get("editor", 0) + 1
            if self.calls["editor"] == 1:
                return AIMessage(content="REVISE please add detail", usage_metadata=_usage())
            return AIMessage(content="APPROVED final text", usage_metadata=_usage())
        if "Writer" in system:
            return AIMessage(content="a draft summary", usage_metadata=_usage())
        if "Researcher" in system:
            return AIMessage(content="finding 1; finding 2", usage_metadata=_usage())
        return AIMessage(content="ok done", usage_metadata=_usage())


def _usage() -> dict:
    return {"input_tokens": 12, "output_tokens": 6, "total_tokens": 18}


@pytest.fixture
def fake_llm(monkeypatch):
    fake = FakeLLM()
    monkeypatch.setattr("app.runtime.agent_node.build_llm", lambda *a, **k: fake)
    monkeypatch.setattr("app.runtime.engine.build_llm", lambda *a, **k: fake)
    return fake
