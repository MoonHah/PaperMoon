# PaperMoon

面向论文与技术文档的 RAG + Agent 智能阅读平台。

## 当前阶段

Phase 13 — Agent 升级。在 RAG 问答之上，引入 LLM function calling 驱动的多步 Agent（ReAct）：自主选择工具、多步推理、按需检索/总结/对比/做笔记。

已具备能力：

- **文档**：上传 `.pdf` / `.md` / `.txt`（Docling 高精度 PDF 解析），内容指纹去重。
- **检索**：Simple / Multi-Query / HyDE 多策略可插拔（`RETRIEVAL_MODE` 切换）+ 离线评估脚本（Hit Rate / MRR）。
- **问答**：单轮 RAG 问答（支持流式）。
- **Agent**：function calling 选工具 + 多步 ReAct loop（详见下方「智能 Agent」）。

## 技术栈

- Python 3.12 / FastAPI / Pydantic Settings / uv
- PostgreSQL 16 / Qdrant / Redis 7
- Celery（异步任务）/ Alembic（数据库迁移）
- Tenacity（LLM 重试）/ Docker / Docker Compose

---

## Docker Compose 快速启动（推荐）

### 前置要求

- Docker Desktop 已安装并运行

### 1. 配置环境变量

```bash
cp .env.example .env
```

打开 `.env`，填写以下必填项：

```env
OPENAI_API_KEY=sk-...        # 必填，用于 embedding 和问答
LLM_MODE=openai
EMBEDDING_MODE=openai
```

数据库 / Redis / Qdrant 的连接地址由 `docker-compose.yml` 自动注入，`.env` 里无需修改。

### 2. 构建镜像

```bash
docker compose build
```

### 3. 启动所有服务

```bash
docker compose up -d
```

启动顺序：postgres → redis → qdrant → api → worker

### 4. 运行数据库迁移（首次启动必须执行一次）

```bash
docker compose exec api alembic upgrade head
```

### 5. 验证服务

```bash
# 存活探针（liveness）
curl http://localhost:8008/api/v1/health
# 返回: {"status": "ok", "app_name": "PaperMoon", "app_version": "0.1.0"}

# 就绪探针（readiness）— 检查 postgres / qdrant / redis
curl http://localhost:8008/api/v1/ready
# 返回: {"status": "ok", "dependencies": {"postgres": "ok", "qdrant": "ok", "redis": "ok"}}
```

接口文档：[http://localhost:8008/docs](http://localhost:8008/docs)

---

## 常用运维命令

### 查看服务状态

```bash
docker compose ps
```

### 查看日志

```bash
# API 服务日志
docker compose logs api

# Worker 日志（查看文档处理进度）
docker compose logs worker

# 实时跟踪 worker 日志
docker compose logs -f worker
```

### 停止 / 重启

```bash
docker compose down          # 停止并移除容器（数据卷保留）
docker compose restart api   # 单独重启 api
```

### 代码变更后重新部署

```bash
docker compose build api worker
docker compose up -d --force-recreate api worker
```

---

## 运行测试

测试无需启动任何外部服务（使用 SQLite 内存库 + Mock 替换真实 LLM/向量库）。

### 主应用测试（40 个）

```bash
# 全部运行
uv run pytest tests/ -v

# 只运行某个模块
uv run pytest tests/test_documents.py -v
uv run pytest tests/test_task.py -v
```

### model-service 测试（10 个）

```bash
cd model_service
python -m pytest tests/ -v
```

---

## 环境变量说明

### LLM 弹性配置

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `LLM_TIMEOUT` | `30.0` | OpenAI chat 调用超时（秒） |
| `LLM_MAX_RETRIES` | `3` | 超时/连接失败后的最大 tenacity 重试次数 |
| `EMBEDDING_TIMEOUT` | `10.0` | OpenAI embedding 调用超时（秒） |
| `EMBEDDING_MAX_RETRIES` | `3` | embedding 最大重试次数 |

LLM 全部重试失败后自动 fallback 到 MockLLMService，响应带 `[MOCK]` 前缀，warning 日志中包含 `request_id`。

### API 限流配置

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `RATE_LIMIT_ENABLED` | `true` | 是否启用限流，设为 `false` 全局关闭 |
| `RATE_LIMIT_REQUESTS` | `60` | 每个 window 内允许的最大请求数 |
| `RATE_LIMIT_WINDOW` | `60` | 计数窗口大小（秒） |

限流 key 优先使用请求头 `X-User-ID`，不存在时退回到客户端 IP。超限返回 HTTP 429：

```json
{"error_code": "RATE_LIMITED", "message": "Rate limit exceeded. Max 60 requests per 60s.", "details": {"limit": 60, "window_seconds": 60}}
```

Redis 不可用时自动跳过限流检查（fail open），不影响正常请求。

### 请求 ID（request_id）

每个请求自动生成 8 位 hex request_id，也可由客户端通过 `X-Request-ID` 请求头透传（便于前后端链路追踪）。  
响应头中始终携带 `X-Request-ID`，所有 JSON 日志包含 `"request_id"` 字段。

### 统一错误响应格式

所有业务异常统一返回：

```json
{
  "error_code": "VALIDATION_ERROR",
  "message": "Request validation failed",
  "details": {}
}
```

---

## 测试文档上传与问答

### 上传文档

```bash
curl -X POST http://localhost:8008/api/v1/documents/upload \
  -F "file=@your_paper.md"
```

返回 `document_id` 和 `task_id`。

### 查询处理状态

```bash
curl http://localhost:8008/api/v1/documents/{document_id}/status
```

状态流转：`UPLOADED → PARSING → CHUNKING → EMBEDDING → INDEXING → READY`

### 发起问答（单轮 RAG）

```bash
curl -X POST http://localhost:8008/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"query": "这篇论文的核心贡献是什么？"}'
```

---

## 智能 Agent（多步推理）

除了单轮问答，还可以让 Agent 自主决策——它用 LLM function calling 选择工具、多步推理（ReAct），按需检索、总结、对比或生成笔记。

```bash
# 让 Agent 自己决定怎么做（自动选工具 + 多步推理；可不提供 document_ids）
curl -X POST http://localhost:8008/api/v1/agent/run \
  -H "Content-Type: application/json" \
  -d '{"user_query": "对比 sample.pdf 和 2503.07919v3.pdf 这两篇文档"}'

# 也可显式指定文档（前端已选定文档的场景）
curl -X POST http://localhost:8008/api/v1/agent/run \
  -H "Content-Type: application/json" \
  -d '{"user_query": "总结这篇文档", "document_ids": ["<document_id>"]}'
```

返回字段：`final_answer`（最终答案）、`selected_tool`、`intermediate_steps`（多步推理轨迹）、`citations`（引用片段）。

### Agent 可用工具

| 工具 | 用途 |
| --- | --- |
| `search_documents` | 检索文档片段，回答具体问题（默认） |
| `summarize_document` | 总结某一篇完整文档 |
| `compare_documents` | 对比两篇或多篇文档的异同 |
| `generate_markdown_notes` | 生成结构化 Markdown 学习笔记 |
| `list_documents` | 列出可用文档，供 Agent 把「那两篇」解析成真实 document_id |

### 工作机制

Agent 用 OpenAI function calling 选工具，在多步 ReAct 循环中把工具结果回填对话历史，直到给出最终答案（最多 5 步，防死循环）。工具执行失败会把错误信息回填，Agent 可感知失败并换策略重试。用户用自然语言指代文档（如「那两篇」）时，Agent 会先调 `list_documents` 拿到真实 document_id 再操作。

---

## 常见启动失败原因

| 症状                        | 原因                                       | 解决方法                                                |
| --------------------------- | ------------------------------------------ | ------------------------------------------------------- |
| `api` 容器反复重启        | 数据库未就绪或迁移未执行                   | 等 postgres `healthy` 后执行 `alembic upgrade head` |
| worker 无法连接 Redis       | Redis 容器未启动                           | `docker compose ps` 确认 redis 状态                   |
| 上传后文档一直 `UPLOADED` | Worker 没有启动或崩溃                      | `docker compose logs worker` 查看错误                 |
| `403 Forbidden` 拉取镜像  | Docker Hub 镜像源失效                      | Docker Desktop Settings → 清空 registry-mirrors        |
| grpcio 编译超时             | Dockerfile 缺少 `--platform=linux/amd64` | 确认 FROM 指令包含平台参数                              |

---

## 本地开发启动（不用 Docker）

```bash
# 启动依赖服务（需要本地 Docker）
docker start postgres_pm qdrant_pm redis_pm

# 启动 API
uv run start

# 启动 Worker（新终端）
uv run celery -A app.workers.celery_app.celery_app worker --loglevel=info
```
