# Demo Guide — AI Agent Orchestration Platform

A step-by-step script for recording the required demo video/gif and for the live
walkthrough. Target length: **3–5 minutes**.

---

## 0. Before you hit record

1. **Lift the Gemini rate limit (recommended).** The free tier allows only a few
   requests/minute, which can 429 a multi-agent run mid-demo. Enable billing on
   the Google Cloud project behind your API key (or keep runs to the 2-agent
   Support Triage flow, which uses fewer calls).
2. **Confirm `.env` is set** (repo root): `GOOGLE_API_KEY`, `TELEGRAM_BOT_TOKEN`,
   `DEFAULT_MODEL=gemini-2.5-flash`.
3. **Start both servers** (two terminals):
   ```powershell
   ./scripts/run-backend.ps1     # http://localhost:8000  (wait for "Telegram bot is polling")
   ./scripts/run-frontend.ps1    # http://localhost:5173
   ```
4. Open **http://localhost:5173** and have **Telegram** open with your bot.
5. Screen-record the browser + Telegram side by side if you can.

---

## 1. Opening (20s) — what it is

> "This is an AI Agent Orchestration Platform. You can create AI agents,
> configure their behaviour, wire them into multi-agent workflows that run on a
> real LangGraph runtime, talk to one over Telegram, and watch everything live."

Show the top nav: **Agents · Workflows · Live Monitor**, and point to the green
**Gemini** and **Telegram** status dots (top-right) — both lit = both connected.

---

## 2. Agents (45s) — configurability

Go to **Agents**. Click **Triage Agent** to show the config surface:
- role, system prompt (personality), model, temperature, max tokens
- **tools** (toggle chips), **channels** (note `telegram`), skills,
  **guardrails**, interaction rules, memory window

> "Every agent has ~13 configurable dimensions. Guardrails and interaction rules
> are injected into the system prompt on every turn."

Optionally click **+ New**, type a name + prompt, toggle the `calculator` tool,
**Save** — show it appears in the list. (This demonstrates Agent CRUD.)

---

## 3. Workflow builder (45s) — branching & loops

Go to **Workflows → Customer Support Triage**.
- Point out the **graph canvas**: Triage → (Technical | Billing). The entry node
  is highlighted.
- Click the **Triage → Billing** edge → the condition panel shows
  `contains "BILLING"`. 

> "The visual graph IS the runtime. Each node is an agent; each edge carries a
> condition. This one branches on the triage agent's classification."

Then open **Research & Review** and point to the **Editor → Writer** edge
(`contains "REVISE"`):

> "This edge points backwards — a feedback loop. The Editor sends the draft back
> to the Writer until it replies APPROVED. The graph recursion limit guarantees
> it terminates."

---

## 4. Run it from the UI (45s) — real execution

On **Customer Support Triage**, in the run box at the bottom type:

> `My card was charged twice this month, I need a refund`

Click **Run**. Narrate as messages stream in:
- Triage Agent → **BILLING**
- Billing Support → a real, helpful refund reply
- Header shows **status, tokens, and cost in USD**

> "Two agents, real Gemini calls, the triage result routed to billing — and the
> cost is tracked live."

---

## 5. Live Monitor (30s) — observability

Go to **Live Monitor** (keep it open in a second tab during the run if possible).

> "Every run streams here over a WebSocket: node starts, tool calls, every
> inter-agent message, and running token/cost totals. The right panel keeps a
> history of all runs with per-run cost."

Point to the **Totals** card and the **Recent runs** list.

---

## 6. Telegram (45s) — the external channel ⭐

This is the headline requirement. In Telegram, message your bot:

> `/start`
> `I was double charged and need a refund`

Show the bot reply in Telegram. **Then switch to the Live Monitor** — the same
conversation is there, tagged `via telegram`.

> "A human is talking to the agent over Telegram, the message ran through the
> exact same multi-agent workflow, and it's all captured live in the platform."

---

## 7. Close (20s) — architecture & honesty

> "Three clean layers — React UI, a FastAPI + LangGraph runtime, and SQLAlchemy
> persistence — decoupled by an event bus. Adding a tool, a template, or a new
> channel is a one-file change. It runs fully local; tests cover the critical
> paths. Thanks for watching."

---

## Talking points for the live code walkthrough (Round 1)

Be ready to open these and explain them:

| Topic | File | One-liner |
|---|---|---|
| Workflow → graph compilation | `backend/app/runtime/engine.py` | Stored nodes/edges → LangGraph `StateGraph`; conditional edges = branching + loops |
| An agent's turn | `backend/app/runtime/agent_node.py` | System prompt from config → Gemini + tools → bounded tool loop |
| Routing | `engine.py::_make_router` | `contains` (deterministic) → `llm` (router model) → `always` fallback |
| Live monitoring | `backend/app/runtime/events.py` | In-process async pub/sub fan-out → WebSocket |
| Cost tracking | `backend/app/runtime/llm.py` | Token usage off each call × a pricing table |
| Telegram | `backend/app/channels/telegram.py` | Long-poll (no public URL) → same `run_workflow` |
| Persistence | `backend/app/models.py` | Agent/Workflow/Run/Message/LogEvent |

**Be honest about the trade-offs** (interviewers respect this):
- `schedule` is modelled but not yet executed — listed under README "future work".
- Event bus is in-process (single node); the seam to swap for Redis/NATS is the
  `EventBus` class.
- Free-tier Gemini rate-limits fast multi-agent runs; production would add
  retry/backoff and billing.
- `web_search` depends on DuckDuckGo being reachable; it degrades gracefully when
  it isn't.

## If something fails on camera
- **429 / quota error** → you're rate-limited; wait ~30s or use the 2-agent
  Support Triage flow (fewer calls). Enabling billing removes this.
- **Telegram not replying** → check the backend log shows `Telegram bot is
  polling`; ensure only one instance of the backend is running (two pollers
  conflict).
- **Empty web results** → expected on some networks; the agent will say results
  weren't available and answer from its own knowledge.
