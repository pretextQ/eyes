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
COPY integrations ./integrations
COPY --from=mewcode pyproject.toml uv.lock README.md /opt/mewcode/
COPY --from=mewcode mewcode /opt/mewcode/mewcode
RUN uv export --project /opt/mewcode --frozen --no-dev --no-emit-project --no-hashes --output-file /tmp/mewcode.txt \
    && /app/.venv/bin/python -c "import importlib.metadata as m,pathlib; names={d.metadata['Name'].lower().replace('_','-') for d in m.distributions()}; lines=pathlib.Path('/tmp/mewcode.txt').read_text().splitlines(); pathlib.Path('/tmp/mewcode-extras.txt').write_text('\n'.join(l for l in lines if l and not l.startswith('#') and l.split('==')[0].lower().replace('_','-') not in names)+'\n')" \
    && uv pip install --python /app/.venv/bin/python --no-deps -r /tmp/mewcode-extras.txt /opt/mewcode \
    && uv pip check --python /app/.venv/bin/python \
    && useradd --create-home --uid 10001 eyes && mkdir -p /app/data/artifacts \
    && chown -R eyes:eyes /app/data && chmod 0700 /app/data/artifacts
ENV PYTHONPATH=/app:/opt/mewcode
ENV PATH=/app/.venv/bin:$PATH
USER eyes
CMD ["uvicorn", "eyes.server.api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
