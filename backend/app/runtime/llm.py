"""Gemini LLM wrapper with token + cost accounting.

Wraps `ChatGoogleGenerativeAI` so the rest of the runtime gets:

* a single place that knows how to build a model from an Agent config, and
* automatic extraction of token usage + a USD cost estimate from every call.

Pricing is a small static table (USD per 1M tokens). Google's published prices
change, so these are *estimates* surfaced for relative cost visibility — the
table is the one place to update if prices move (called out in the README).
"""
from __future__ import annotations

from dataclasses import dataclass

from langchain_core.messages import AIMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from app.config import get_settings

# USD per 1,000,000 tokens: (input, output). Keep keys lowercase.
_PRICING: dict[str, tuple[float, float]] = {
    "gemini-2.5-flash": (0.30, 2.50),
    "gemini-2.5-flash-lite": (0.10, 0.40),
    "gemini-2.5-pro": (1.25, 10.00),
    "gemini-2.0-flash": (0.10, 0.40),
    "gemini-2.0-flash-lite": (0.075, 0.30),
    "gemini-flash-latest": (0.30, 2.50),
}
_DEFAULT_PRICE = (0.30, 2.50)


@dataclass
class Usage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_usd: float = 0.0


def estimate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    in_price, out_price = _PRICING.get(model.lower(), _DEFAULT_PRICE)
    return round(
        (prompt_tokens / 1_000_000) * in_price
        + (completion_tokens / 1_000_000) * out_price,
        6,
    )


def extract_usage(model: str, response: AIMessage) -> Usage:
    """Pull token counts off a LangChain AIMessage and price them."""
    meta = getattr(response, "usage_metadata", None) or {}
    prompt = int(meta.get("input_tokens", 0) or 0)
    completion = int(meta.get("output_tokens", 0) or 0)
    return Usage(
        prompt_tokens=prompt,
        completion_tokens=completion,
        cost_usd=estimate_cost(model, prompt, completion),
    )


def build_llm(
    model: str | None = None,
    temperature: float = 0.3,
    max_tokens: int = 1024,
) -> ChatGoogleGenerativeAI:
    """Construct a Gemini chat model bound to the configured API key.

    NOTE on Gemini 2.5 "thinking": the 2.5 models reason internally and that
    reasoning consumes the output-token budget. With a modest `max_output_tokens`
    a model can spend the entire budget thinking and emit *zero* visible text.
    We therefore disable thinking (`thinking_budget=0`) — our agents don't need
    chain-of-thought, and this makes outputs reliable and cheaper. The kwarg is
    ignored by non-thinking models, so it's safe across the board.
    """
    settings = get_settings()
    return ChatGoogleGenerativeAI(
        model=model or settings.default_model,
        temperature=temperature,
        max_output_tokens=max_tokens,
        google_api_key=settings.google_api_key,
        thinking_budget=0,
    )
