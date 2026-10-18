# SupportPilot

A LangGraph + FastAPI customer-support AI agent that answers from a RAG knowledge base, calls tools (orders, returns, appointments, CRM), and hands off to a human — with a Next.js UI.

> **Self-built portfolio demo** using mock store data. Developed with AI-assisted coding (Cursor); architecture, review, and testing by the author. Not a production product.

## Quick start

```bash
cp .env.example .env
# Optional: set LLM_API_KEY / LLM_* when you reach agent milestones.
docker compose up --build
```

URLs (after containers are healthy):

| Service  | URL |
|----------|-----|
| Frontend | http://127.0.0.1:3000 |
| Backend health | http://127.0.0.1:8000/api/health |
| OpenAPI docs | http://127.0.0.1:8000/docs |
| Postgres | `localhost:5432` (user/db/password: `supportpilot`) |

## Local development (without Docker for apps)

### Backend

```bash
cd backend
uv sync --all-groups
uv run uvicorn app.main:app --reload --port 8000
```

Checks: `uv run ruff check .` · `uv run mypy app` · `uv run pytest`

### Frontend

```bash
cd frontend
npm ci
npm run dev
```

Checks: `npm run lint` · `npm run build`

Node version: see `.nvmrc` (`22.23.3`).

## Current milestone

Step 1 scaffold: monorepo, health API, placeholder frontend showing backend health, Docker Compose, pre-commit, and GitHub Actions CI. Later milestones add DB models, tools, RAG, the agent, and chat UI.

## License

Portfolio demo — use and adapt with attribution.
