# PaperMoon

面向论文与技术文档的 RAG + Agent 智能阅读平台。

## 当前阶段

Phase 0 — 项目骨架，包含 FastAPI 基础结构与 `/health` 接口。

## 技术栈

- Python 3.11+
- FastAPI
- Pydantic Settings
- uv

## 快速开始

### 1. 安装依赖

```bash
uv sync
```

### 2. 配置环境变量

```bash
cp .env.example .env
```

按需修改 `.env` 中的值。

### 3. 启动服务

```bash
uv run uvicorn app.main:app --host 0.0.0.0 --port 8015 --reload
```

### 4. 访问接口

- 健康检查：<http://localhost:8015/api/v1/health>
- 接口文档：<http://localhost:8015/docs>

## 项目结构

```text
papermoon/
├── app/
│   ├── main.py              # FastAPI 入口，挂载路由
│   ├── api/
│   │   └── v1/
│   │       ├── router.py    # 聚合所有 v1 路由
│   │       └── health.py    # GET /health 接口
│   ├── core/
│   │   └── config.py        # Pydantic Settings 配置
│   └── schemas/             # Pydantic 响应模型（待扩展）
├── tests/
│   └── conftest.py
├── .env.example
├── pyproject.toml
└── README.md
```

## 运行测试

```bash
uv run pytest
```
