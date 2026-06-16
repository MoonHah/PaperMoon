FROM python:3.12-slim

WORKDIR /app

# libgomp1: OpenMP multi-threading for PyTorch inference
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Install dependencies。挂 BuildKit 缓存：已下载的包跨构建/重试持久化，
# 依赖变更或镜像源抖动时不必从零重下全部（含 torch/nvidia 共约 2GB），重试只补缺口。
COPY pyproject.toml uv.lock README.md ./
RUN --mount=type=cache,target=/root/.cache/uv \
    UV_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/ \
    uv sync --no-dev
ENV PATH="/app/.venv/bin:$PATH"

# Copy application code
COPY . .
