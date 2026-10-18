FROM python:3.12.15-slim-bookworm

COPY --from=ghcr.io/astral-sh/uv:0.11.33 /uv /uvx /bin/

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

COPY pyproject.toml uv.lock alembic.ini ./
RUN uv sync --frozen --no-dev --no-install-project

COPY app ./app
COPY scripts ./scripts
COPY seed_kb ./seed_kb
RUN uv sync --frozen --no-dev

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
