FROM python:3.12-slim

WORKDIR /app

# 运行期系统库：
#   libgomp1            PyTorch OpenMP 多线程
#   libgl1/libglib2.0-0 opencv-python（Docling 图像处理）所需
#   libxcb1             opencv 链接的 X protocol 库（缺它解析 PDF 时 ImportError）
# 挂 BuildKit apt 缓存：已下载的 .deb 跨构建/重试持久化，网络抖动时重试只补缺口、不重下全部。
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get -o Acquire::Retries=10 update \
    && apt-get -o Acquire::Retries=10 install -y --no-install-recommends \
      libgomp1 libgl1 libglib2.0-0 libxcb1

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
