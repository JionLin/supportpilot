# SupportPilot User Guide

Detailed how-to for running and demonstrating this **self-built portfolio demo**.  
For a short overview, see the root [README.md](../README.md). For product/spec detail, see [SPEC.md](SPEC.md).

> **Honesty first:** SupportPilot is a self-built demo with **mock store data**. It was developed with **AI-assisted coding** (Cursor); architecture, review, and testing are by the author. It is **not a production product**. Do not invent user counts, revenue, uptime SLAs, or eval pass rates.

---

## 1. What this project is / is not

### Is

- A **LangGraph + FastAPI** customer-support agent with:
  - **RAG** over policy Markdown (citations)
  - **Tool calling** (orders, shipping, returns, appointments, CRM, human handoff)
  - **Next.js** chat UI (SSE streaming) and admin pages (KB, traces, tickets, mock chaos)
- Runnable locally via **Docker Compose** or local backend + frontend against Postgres/pgvector
- Compatible with any **OpenAI-compatible** LLM endpoint via env vars
- Testable without a paid API key (Fake LLM in unit tests; Fake embeddings when `LLM_API_KEY` is empty)

### Is not

- A live Shopify / payment / multi-tenant SaaS product
- A production-hardened deployment with real auth, secrets management, or SLA claims
- A source of fabricated business or eval metrics (`evals/report.md` stays a placeholder until you run real evals)

---

## 2. Prerequisites

| Tool | Notes |
|------|--------|
| **Docker / Docker Compose** | Recommended path: `db` + `backend` + `frontend` |
| **Node.js** | Version from [`.nvmrc`](../.nvmrc): **22.23.3** (use `nvm use` or matching Docker image) |
| **uv** | Python package manager for `backend/` (project targets Python 3.12) |
| **PostgreSQL 16 + pgvector** | Compose uses `pgvector/pgvector:0.8.7-pg16-bookworm`. For local-only apps, run an equivalent Postgres with the `vector` extension |
| **LLM API key (optional)** | Required for live Chat demos and `evals.run_evals`. Empty key → Fake embeddings for RAG/CI; chat calls will not reach a real model |

Also useful: `git`, a browser, and (for demos) Loom/OBS per [demo-script.md](demo-script.md).

---

## 3. Environment variables

Copy the template and edit:

```bash
cp .env.example .env
```

Variables from [`.env.example`](../.env.example):

| Variable | Purpose | Example / default |
|----------|---------|-------------------|
| `LLM_BASE_URL` | OpenAI-compatible API base | `https://api.openai.com/v1` |
| `LLM_API_KEY` | API key (leave empty for Fake embeddings / CI) | *(empty)* |
| `LLM_MODEL` | Chat model id | `gpt-4o-mini` |
| `EMBEDDING_MODEL` | Embedding model id | `text-embedding-3-small` |
| `EMBEDDING_DIM` | Vector dimension (must match model / DB column) | `1536` |
| `DATABASE_URL` | Async SQLAlchemy URL | Compose service: `postgresql+asyncpg://supportpilot:supportpilot@db:5432/supportpilot` · Host migrate/seed: same with `127.0.0.1` |
| `MAX_STEPS` | Agent step budget before handoff | `8` |
| `MAX_TOOL_ERRORS` | Tool error budget before handoff | `3` |
| `REQUEST_TIMEOUT_S` | Request timeout (seconds) | `60` |
| `ADMIN_PASSWORD` | Backend admin header password (`X-Admin-Password`) | `change-me` |
| `MOCK_LATENCY_MS` | Artificial mock API latency | `0` |
| `MOCK_FAILURE_RATE` | Mock API failure probability `0.0`–`1.0` | `0.0` |
| `MOCK_BASE_URL` | Base URL tools use for mock upstreams | `http://127.0.0.1:8000` |
| `WEBHOOK_URL` | Optional POST target on handoff / booking | *(empty)* |
| `NEXT_PUBLIC_API_URL` | Browser → backend origin | `http://127.0.0.1:8000` |
| `NEXT_PUBLIC_ADMIN_PASSWORD` | Frontend admin gate (sent as `X-Admin-Password`) | `change-me` |

Related settings also exist in code (`USE_FAKE_EMBEDDINGS`, `RAG_DISTANCE_THRESHOLD`, CORS origins) via `app.config.Settings`; the table above covers what `.env.example` documents for operators.

### LLM provider examples (OpenAI-compatible)

```bash
# OpenAI
LLM_BASE_URL=https://api.openai.com/v1
LLM_API_KEY=sk-...
LLM_MODEL=gpt-4o-mini
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_DIM=1536

# Qwen (DashScope compatible mode)
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_API_KEY=sk-...
LLM_MODEL=qwen-plus
# Use an embedding model your DashScope account supports; keep EMBEDDING_DIM aligned

# Gemini OpenAI-compatible endpoint
LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
LLM_API_KEY=...
LLM_MODEL=gemini-2.0-flash
```

The backend builds `ChatOpenAI` from `LLM_*` (see `app.agent.llm`). Models must support **tool / function calling** for the agent loop.

---

## 4. Two ways to run

### A. Docker Compose (recommended demo path)

```bash
cp .env.example .env
# Optional live LLM:
# LLM_API_KEY=...   LLM_BASE_URL=...   LLM_MODEL=...

docker compose up --build
```

Then **migrate + seed** from the host against published Postgres (`localhost:5432`):

```bash
cd backend
export DATABASE_URL=postgresql+asyncpg://supportpilot:supportpilot@127.0.0.1:5432/supportpilot
uv sync --all-groups
uv run alembic upgrade head
uv run python -m scripts.seed   # idempotent; safe to re-run
```

Compose services: `db` (pgvector), `backend` (port 8000), `frontend` (port 3000). Backend `DATABASE_URL` inside Compose points at host `db`.

### B. Local backend + frontend (Postgres separately)

1. Run Postgres 16 with pgvector (Compose `db` only is fine: `docker compose up db`).
2. Backend:

```bash
cd backend
export DATABASE_URL=postgresql+asyncpg://supportpilot:supportpilot@127.0.0.1:5432/supportpilot
uv sync --all-groups
uv run alembic upgrade head
uv run python -m scripts.seed
uv run uvicorn app.main:app --reload --port 8000
```

3. Frontend (Node from `.nvmrc`):

```bash
cd frontend
npm ci
npm run dev
```

Ensure `NEXT_PUBLIC_API_URL=http://127.0.0.1:8000` and `MOCK_BASE_URL` can reach the backend from the tool layer.

---

## 5. URLs

| Service | URL |
|---------|-----|
| Frontend (landing / chat / admin) | http://127.0.0.1:3000 |
| Backend health | http://127.0.0.1:8000/api/health |
| OpenAPI (Swagger) | http://127.0.0.1:8000/docs |
| Postgres | `localhost:5432` (user / db / password: `supportpilot`) |

Useful UI routes after start:

| Path | Role |
|------|------|
| `/` | Landing |
| `/chat` | Customer chat |
| `/admin/knowledge` | Knowledge base upload / list |
| `/admin/conversations` | Conversation list + per-session trace |
| `/admin/tickets` | Human-handoff tickets |
| `/admin/settings` | Model/guardrail readout + mock chaos sliders |

---

## 6. Using the Chat UI

Open http://127.0.0.1:3000/chat.

**For a meaningful live demo, set `LLM_API_KEY` (and matching `LLM_BASE_URL` / `LLM_MODEL`).** Without a key, embeddings use a deterministic Fake embedder (good for CI/seed); the chat path still constructs a real `ChatOpenAI` client and will not behave like the Fake LLM used in unit tests.

### Sample questions (also as UI chips)

From `frontend/app/chat/page.tsx`:

1. `What is your return policy?` — RAG FAQ; expect **citations** (document name + snippet).
2. `Where is order A1001? email jane@example.com` — `get_order` (+ shipping as needed); order card when verified.
3. Wrong email for the same order (e.g. `Where is order A1001? email wrong@example.com`) — **dual check**: order_id + email must match; no data leak on mismatch.
4. `I want to return order A1003, email sam@example.com` — return window OK → RMA via `create_return_request`. Seed **A1005** / older delivered orders demonstrate **out-of-window** refusal.
5. `Book a call-back for jane@example.com tomorrow` — `check_availability` then `book_appointment`.
6. `I need to talk to a human` — `handoff_to_human` → ticket id; conversation status `handed_off`.

Streaming uses SSE (`Accept: text/event-stream`): `token`, `tool_end`, `citation`, `final`, `error`.

### Seed orders worth remembering

| Order | Email | Typical demo use |
|-------|-------|------------------|
| A1001 | jane@example.com | In-transit lookup |
| A1003 | sam@example.com | Valid return / RMA |
| A1005 | casey@example.com | Past return window |

Full seed set: `backend/scripts/seed.py` + `backend/seed_kb/*.md`.

---

## 7. Admin

Admin pages are behind a shared password gate. Use the same value as `ADMIN_PASSWORD` / `NEXT_PUBLIC_ADMIN_PASSWORD` (default `change-me`). The browser sends `X-Admin-Password`.

| Area | What to do |
|------|------------|
| **Knowledge** (`/admin/knowledge`) | List documents; upload Markdown/PDF or submit a URL; watch ingest status / chunk counts; delete docs |
| **Conversations** (`/admin/conversations`) | List sessions; open a session for **trace** (nodes, tool I/O, latency, attempts, errors) |
| **Tickets** (`/admin/tickets`) | List handoff tickets; update status (`open` / `in_progress` / `resolved`) |
| **Settings** (`/admin/settings`) | Read current LLM/guardrail/RAG settings; adjust **mock failure rate** and **latency** (chaos) to demo retries → handoff |

API counterparts (OpenAPI at `/docs`): `/api/kb/*`, `/api/conversations/*`, `/api/tickets`, `/api/admin/settings`, `/api/admin/mock-chaos`.

---

## 8. Tools and guardrails

### Tools

Registered in `app.tools.registry` (schemas via `get_openai_tools_schema()`, aligned with SPEC §7):

| Tool | Role |
|------|------|
| `search_knowledge_base` | RAG search before policy answers |
| `get_order` | Order lookup; **requires order_id + email** |
| `track_shipment` | Tracking events for a tracking number |
| `create_return_request` | Create RMA when policy/window allows |
| `check_availability` | List call-back slots |
| `book_appointment` | Book a slot |
| `upsert_crm_contact` | Upsert mock CRM lead |
| `handoff_to_human` | Create ticket and hand off |

Mock upstreams (same FastAPI process): `/mock/orders/...`, `/mock/shipping/...`, `/mock/calendar/...`, `/mock/crm/contacts`, `/mock/returns`.

### Guardrails

| Guard | Behavior |
|-------|----------|
| Tool timeout / HTTP 5xx | tenacity backoff, **max 3 attempts**; each attempt traced |
| Tool 4xx / business errors | **no** retry; structured error to the LLM |
| `MAX_STEPS` (default 8) | → handoff (`low_confidence`) |
| `MAX_TOOL_ERRORS` (default 3) | → handoff (`tool_failure`) |
| Structured output failure | plain-text fallback, low confidence |
| Order tools | order_id + email must match or 404 (no leak) |
| `WEBHOOK_URL` | optional on handoff/booking; retries up to 3×; never blocks the user reply |

LangGraph flow: `guard → agent ⇄ tools → finalize | handoff` (see architecture below).

---

## 9. Tests and evals

### Quality checks / unit tests (no API key required)

```bash
cd backend
uv run ruff check .
uv run mypy app
uv run pytest
```

Agent graph tests inject **`ScriptedFakeChatModel`** (`app.agent.fake_llm`) — no network.  
When `LLM_API_KEY` is empty, embeddings use **FakeEmbedder** (deterministic vectors).

Frontend:

```bash
cd frontend
npm ci
npm run lint
npm run build
```

### Evals (real LLM only)

```bash
cd backend
# Refuses to invent scores if LLM_API_KEY is unset (exit code 2)
uv run python -m evals.run_evals
```

- Cases: `backend/evals/cases.yaml`
- Report: `backend/evals/report.md` — ships as a **placeholder** with **no fabricated metrics**; pass rates appear only after a real run (model, date, case count recorded by the script)

---

## 10. Demo script

Shot list for a 2–3 minute Loom/OBS recording: **[docs/demo-script.md](demo-script.md)**.

---

## 11. Architecture

![SupportPilot architecture](architecture.png)

Source: [architecture.mmd](architecture.mmd) · vector: [architecture.svg](architecture.svg)

**In prose:** The Next.js UI talks REST/SSE to FastAPI. Chat turns enter a LangGraph agent: `guard` checks input/safety and handed-off state; `agent` calls an OpenAI-compatible LLM with tools bound; `tools` validates args, applies timeout/retry, and talks to **pgvector RAG** and **mock store APIs**; successful completion goes through `finalize` (structured `AgentReply`); step/error limits or an explicit handoff tool go to `handoff` (ticket + optional `WEBHOOK_URL`). Conversation state, traces, KB chunks, and tickets live in **PostgreSQL + pgvector**.

The same diagram appears as Mermaid in the root README.

---

## 12. Known limitations

- Mock store / calendar / CRM only — no real Shopify, payments, or multi-tenant auth
- Admin auth is a shared password header for demo purposes only
- Without `LLM_API_KEY`, embeddings are fake (fine for CI); live Chat needs a real tool-calling model for demos
- Optional n8n workflow example (SPEC M11) is not included
- Eval numbers exist only after you run `evals.run_evals` with a real key — never invent them for portfolio claims

---

## 13. Related docs

| Doc | Audience |
|-----|----------|
| [README.md](../README.md) | GitHub / Upwork landing summary |
| [USER_GUIDE.md](USER_GUIDE.md) | This English how-to |
| [docs/zh/使用说明书.md](zh/使用说明书.md) | Author learning notes (Simplified Chinese) |
| [SPEC.md](SPEC.md) | Full build/spec document |
| [demo-script.md](demo-script.md) | Video shot list |
