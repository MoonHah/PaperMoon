FROM python:3.12-slim

WORKDIR /app

# libgomp1: OpenMP multi-threading for PyTorch inference
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Install dependencies (cached layer)
COPY pyproject.toml uv.lock README.md ./
RUN UV_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple \
    uv sync --no-dev
ENV PATH="/app/.venv/bin:$PATH"

# Copy application code
COPY . .
