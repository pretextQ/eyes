FROM python:3.12-slim
ENV UV_PYTHON_INSTALL_DIR=/opt/python
RUN python -m pip install --no-cache-dir --index-url https://pypi.org/simple uv \
    && uv python install 3.14.7 \
    && uv venv /app/.venv --python 3.14.7
WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
COPY alembic.ini ./
COPY migrations ./migrations
COPY integrations ./integrations
COPY --from=mewcode pyproject.toml README.md /opt/mewcode/
COPY --from=mewcode mewcode /opt/mewcode/mewcode
RUN uv pip install --python /app/.venv/bin/python --index-url https://pypi.org/simple /app /opt/mewcode \
    && useradd --create-home --uid 10001 eyes && mkdir -p /app/data/artifacts \
    && chown -R eyes:eyes /app/data
ENV PYTHONPATH=/app:/opt/mewcode
ENV PATH=/app/.venv/bin:$PATH
USER eyes
CMD ["uvicorn", "eyes.server.api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
