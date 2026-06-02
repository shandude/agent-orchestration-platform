"""Telegram channel — lets a human chat with an agent over Telegram.

We use long-polling (not webhooks) so the platform works fully locally with no
public URL or tunnel — important for the "single setup command" requirement.

When a user messages the bot, we run the *Telegram-bound* workflow (the one
whose entry agent lists "telegram" in its channels) and reply with the result.
The same run is persisted and broadcast on the monitoring WebSocket, so a
Telegram conversation shows up live in the web UI too.

Adding another channel (Slack/WhatsApp) means writing a sibling module with the
same shape: receive text → `engine.run_workflow(...)` → send the reply.
"""
from __future__ import annotations

import logging

from app.config import get_settings
from app.database import SessionLocal
from app.models import Agent, Workflow
from app.runtime.engine import run_workflow

logger = logging.getLogger("channels.telegram")

# Holds the running python-telegram-bot Application (set on startup).
_application = None


def _find_telegram_workflow() -> Workflow | None:
    """Pick the workflow a Telegram message should trigger."""
    with SessionLocal() as db:
        # Prefer a workflow whose entry node is an agent bound to telegram.
        workflows = db.query(Workflow).all()
        for wf in workflows:
            entry = wf.entry_node or (wf.nodes[0]["id"] if wf.nodes else None)
            node = next((n for n in (wf.nodes or []) if n["id"] == entry), None)
            if not node:
                continue
            agent = db.get(Agent, node["agent_id"])
            if agent and "telegram" in (agent.channels or []):
                return wf
        # Fallback: the support template, else the first workflow.
        return (
            db.query(Workflow).filter(Workflow.name == "Customer Support Triage").first()
            or (workflows[0] if workflows else None)
        )


async def _on_start(update, context) -> None:  # noqa: ANN001
    await update.message.reply_text(
        "👋 You're connected to the Agent Orchestration Platform.\n"
        "Send me a message and I'll route it through the live agent workflow."
    )


async def _on_message(update, context) -> None:  # noqa: ANN001
    text = (update.message.text or "").strip()
    if not text:
        return
    wf = _find_telegram_workflow()
    if wf is None:
        await update.message.reply_text("No workflow is configured yet.")
        return
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    try:
        _, output = await run_workflow(wf.id, text, trigger="telegram")
        await update.message.reply_text(output or "(no response produced)")
    except Exception as exc:  # noqa: BLE001
        logger.exception("Telegram run failed")
        await update.message.reply_text(f"⚠️ Something went wrong: {exc}")


async def start_telegram() -> None:
    """Start the bot inside the running event loop (called from app lifespan)."""
    global _application
    settings = get_settings()
    if not settings.telegram_enabled:
        logger.info("Telegram disabled (no TELEGRAM_BOT_TOKEN).")
        return

    from telegram.ext import (
        Application,
        CommandHandler,
        MessageHandler,
        filters,
    )

    _application = Application.builder().token(settings.telegram_bot_token).build()
    _application.add_handler(CommandHandler("start", _on_start))
    _application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, _on_message)
    )

    await _application.initialize()
    await _application.start()
    await _application.updater.start_polling(drop_pending_updates=True)
    logger.info("Telegram bot is polling.")


async def stop_telegram() -> None:
    global _application
    if _application is None:
        return
    try:
        await _application.updater.stop()
        await _application.stop()
        await _application.shutdown()
    finally:
        _application = None
