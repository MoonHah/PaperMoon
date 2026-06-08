FROM --platform=linux/amd64 python:3.12-slim

WORKDIR /service

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Install dependencies (cached layer — only rebuilds when pyproject.toml changes)
COPY pyproject.toml .
RUN uv pip install --system --no-cache-dir \
    "fastapi>=0.115.0" \
    "uvicorn[standard]>=0.30.0" \
    "openai>=1.50.0" \
    "tenacity>=9.0.0" \
    "pydantic-settings>=2.5.0"

# Copy source
COPY app/ ./app/

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8009"]
