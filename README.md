# SupportPilot

> A LangGraph + FastAPI customer-support AI agent that answers from a RAG knowledge base, calls tools (order lookup, returns, appointment booking, CRM), returns structured JSON, and hands off to a human — with a Next.js chat UI and admin trace viewer.

**Self-built portfolio demo** using mock store data. Built with AI-assisted development (Cursor); architecture, review, and testing by the author. **Not a production product.** No customer deployment claims, no invented business metrics.

![Architecture](docs/architecture.png)

## Features

- **RAG Q&A** with citations from uploaded / seeded Markdown policies
- **Tool calling**: `search_knowledge_base`, `get_order`, `track_shipment`, `create_return_request`, `check_availability`, `book_appointment`, `upsert_crm_contact`, `handoff_to_human`
- **Guardrails**: `MAX_STEPS`, `MAX_TOOL_ERRORS`, tool timeouts + tenacity retries (5xx/timeout only), order+email dual verification, structured `AgentReply`
- **Observability**: per-step traces (tool I/O, latency, attempts, errors)
- **Chat UI** (SSE streaming) + **Admin** (knowledge base, conversations/trace, tickets, mock chaos slider)
- **Eval harness** (`backend/evals`) — numbers only from real LLM runs

## Architecture

```mermaid
flowchart LR
  UI[Next.js UI] -->|REST + SSE| API[FastAPI]
  API --> G[LangGraph]
  G --> Guard --> Agent --> Tools
  Tools --> Agent
  Agent --> Finalize
  Agent --> Handoff
  Tools --> RAG[(pgvector)]
  Tools --> Mock[Mock store APIs]
```

LangGraph nodes: `guard → agent ⇄ tools → finalize | handoff`.

## Quick start

```bash
cp .env.example .env
# Optional for live LLM demos:
# LLM_API_KEY=...
# LLM_BASE_URL=https://api.openai.com/v1
# LLM_MODEL=gpt-4o-mini

docker compose up --build
```

Migrate + seed (from host against published Postgres):

```bash
cd backend
export DATABASE_URL=postgresql+asyncpg://supportpilot:supportpilot@127.0.0.1:5432/supportpilot
uv sync --all-groups
uv run alembic upgrade head
uv run python -m scripts.seed
```

| Service | URL |
|---------|-----|
| Frontend | http://127.0.0.1:3000 |
| Backend health | http://127.0.0.1:8000/api/health |
| OpenAPI | http://127.0.0.1:8000/docs |

Without Docker for apps: run Postgres (pgvector), then `uv run uvicorn app.main:app --reload --port 8000` and `npm run dev` in `frontend/`.

## LLM provider examples

Chat via OpenAI-compatible `ChatOpenAI` (`LLM_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL`). Embeddings use optional `EMBEDDING_BASE_URL` / `EMBEDDING_API_KEY` (empty → reuse `LLM_*`):

```bash
# OpenAI
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o-mini

# Qwen (DashScope compatible mode)
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_MODEL=qwen-plus

# Gemini OpenAI-compatible endpoint
LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
LLM_MODEL=gemini-2.0-flash
```

Tests and CI use **Fake LLM / Fake embeddings** — no API key required (Fake embeddings when the resolved embedding key is unset).

## API & tools

- `POST /api/chat` — JSON `AgentReply`, or SSE (`Accept: text/event-stream`) events: `token`, `tool_end`, `citation`, `final`, `error`
- `GET /api/conversations`, `/{id}`, `/{id}/trace`
- `POST/GET/DELETE /api/kb/documents`, `POST /api/kb/search`
- `GET/PATCH /api/tickets`, `GET /api/appointments`
- `GET /api/admin/settings`, `PUT /api/admin/mock-chaos` (header `X-Admin-Password`)
- Mock upstream: `/mock/orders/{id}?email=`, `/mock/shipping/{tracking}`, `/mock/calendar/*`, `/mock/crm/contacts`, `/mock/returns`

Tool JSON Schema matches `docs/SPEC.md` §7 (exported by `app.tools.get_openai_tools_schema()`).

## Errors & guardrails

| Guard | Behavior |
|-------|----------|
| Tool timeout / 5xx | tenacity exponential backoff, max 3 attempts; each attempt traced |
| Tool 4xx / business errors | no retry; clear error code to the LLM |
| `MAX_STEPS=8` | handoff (`low_confidence`) |
| `MAX_TOOL_ERRORS=3` | handoff (`tool_failure`) |
| Structured output failure | plain-text fallback, `confidence=0.3` |
| Order tools | order_id + email must match or 404 (no leak) |
| Webhook | optional `WEBHOOK_URL` on handoff/booking (retry 3×, never blocks reply) |

## Tests & evals

```bash
cd backend
uv run ruff check .
uv run mypy app
uv run pytest

cd ../frontend
npm ci && npm run lint && npm run build
```

**Evals (real LLM only):**

```bash
cd backend
# writes evals/report.md ONLY when LLM_API_KEY is set
uv run python -m evals.run_evals
```

`evals/report.md` ships as a placeholder stating that **no fabricated metrics** are present. Pass rates appear only after a real run (model + date + case count recorded by the script).

## Documentation

- **[docs/USER_GUIDE.md](docs/USER_GUIDE.md)** — English how-to (run, env vars, Chat/Admin, tools, tests, limitations). Prefer this for GitHub / Upwork.
- **[docs/zh/使用说明书.md](docs/zh/使用说明书.md)** — Simplified Chinese notes for the author to learn the project (not the public homepage).
- Architecture diagram: [docs/architecture.png](docs/architecture.png) (source [architecture.mmd](docs/architecture.mmd)); also embedded as Mermaid above.
- Spec: [docs/SPEC.md](docs/SPEC.md)

## Demo script

See [docs/demo-script.md](docs/demo-script.md) for a 2–3 minute Loom/OBS shot list.

## Known limitations

- Mock store / calendar / CRM only — no real Shopify, payments, or multi-tenant auth
- Optional `EMBEDDING_BASE_URL` / `EMBEDDING_API_KEY` (empty → reuse `LLM_*`); Fake embeddings when the resolved embedding key is unset (fine for CI; use a real embedding model for semantic RAG demos)
- Optional n8n workflow (SPEC M11) not included
- Admin auth is a shared password header for demo purposes only

## License

Portfolio demo — use and adapt with attribution.
