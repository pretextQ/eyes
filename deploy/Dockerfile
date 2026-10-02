FROM ghcr.io/astral-sh/uv:0.12.2 AS uv
FROM python:3.14.7-slim
COPY --from=uv /uv /usr/local/bin/uv
WORKDIR /app
ENV UV_LINK_MODE=copy UV_COMPILE_BYTECODE=1
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN uv sync --frozen --no-dev
COPY alembic.ini ./
COPY migrations ./migrations
RUN useradd --create-home --uid 10001 eyes && mkdir -p /app/data/artifacts \
    && chown -R eyes:eyes /app/data
ENV PATH="/app/.venv/bin:$PATH"
USER eyes
CMD ["uvicorn", "eyes.server.api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
