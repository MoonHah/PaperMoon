# 项目：Personal Research Paper RAG & Agent Platform

## 个人论文 / 技术资料智能助手平台

一句话描述：

> 做一个可以上传论文、技术文档、博客资料，然后进行检索问答、总结、对比、生成学习笔记，并逐步工业化部署的 RAG + Agent 项目。

---

# 一、项目最终效果

用户可以上传一批论文或技术文档，比如：

```Plain
RAG 论文
Agent 论文
LangChain 文档
LangGraph 文档
vLLM 文档
MCP 文档
企业知识库文章
```

然后系统支持：

```Plain
1. 基于文档问答
2. 自动总结论文
3. 多篇文档对比
4. 生成 Markdown 学习笔记
5. 根据问题自动选择工具
6. 后台异步解析和向量化文档
7. 查看文档处理状态
8. 记录每次问答链路和模型消耗
```

例如你问：

```Plain
请对比 Multi Query、RAG-Fusion 和 HyDE 的区别。
```

系统会：

```Plain
检索相关文档
→ 找到多个片段
→ 组织答案
→ 给出引用来源
→ 生成 Markdown 笔记
```

这和你最近正在学的 RAG、Multi Query、RRF、Agent 很契合。

---

# 二、为什么这个项目最适合你

因为它同时满足 5 个条件：

| 条件                 | 是否满足                            |
| -------------------- | ----------------------------------- |
| 一个人能做           | 可以                                |
| 数据容易获得         | arXiv、官方文档、技术博客都可以     |
| 能体现大模型应用能力 | RAG、Agent、Prompt、工具调用        |
| 能体现工程能力       | FastAPI、Redis、Celery、Docker、K8s |
| 能写进简历           | 很适合                              |

它不像机器人项目那样需要：

```Plain
摄像头
语音识别
TTS
ROS2
传感器事件
多模态识别
```

这些东西一个人做会很散，容易变成“每个都碰一点，但没有一个做深”。

论文 / 技术资料助手的好处是：
**你可以把精力集中在 RAG、Agent 和工程化上。**

---

# 三、项目名称可以这样写在简历里

你可以叫它：

```Plain
Research Agent: 面向技术文档的企业级 RAG + Agent 学习平台
```

或者：

```Plain
PaperPilot: 基于 RAG 与 Agent 的论文智能阅读与知识管理系统
```

简历表达会比“个人知识库问答系统”更高级一点。

---

# 四、项目核心业务流程

系统主流程：

```Plain
用户上传 PDF / Markdown / TXT
        ↓
后台异步解析文档
        ↓
文本切分 chunk
        ↓
调用 embedding 模型
        ↓
写入向量数据库
        ↓
用户提问
        ↓
RAG 检索相关内容
        ↓
Agent 判断是否需要调用工具
        ↓
LLM 生成答案
        ↓
返回答案 + 引用来源 + 日志记录
```

---

# 五、推荐数据集 / 资料来源

你可以用这些资料作为知识库：

## 第一类：论文

适合做 RAG 测试：

```Plain
Attention Is All You Need
Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks
ReAct: Synergizing Reasoning and Acting in Language Models
Self-RAG
HyDE
Toolformer
MRKL
GraphRAG
```

这些论文都不难找到，而且非常适合大模型应用方向。

## 第二类：官方文档

适合做工程问答：

```Plain
LangChain 官方文档
LangGraph 官方文档
LlamaIndex 官方文档
vLLM 官方文档
Ray Serve 官方文档
FastAPI 官方文档
Celery 官方文档
Kubernetes 官方文档
```

## 第三类：你自己的学习资料

这个最实用：

```Plain
你自己的 Markdown 笔记
导师给你的项目说明
你整理的 RAG / Agent 学习资料
面试八股文
项目 README
```

这样它最后不只是一个 Demo，还能真的变成你的学习工具。

---

# 六、工业化实现路线

你可以严格按照工业项目顺序做。

---

## Phase 1：单体 RAG Demo

目标：先跑通最小业务闭环。

### 技术栈

```Plain
Python
FastAPI
Pydantic
SQLite / PostgreSQL
FAISS / Chroma / Qdrant
OpenAI API / 本地模型 API
```

### 实现功能

```Plain
POST /upload
POST /chat
GET /documents
GET /health
```

最小闭环：

```Plain
上传文档
→ 解析文本
→ 切分 chunk
→ embedding
→ 向量检索
→ LLM 回答
```

这一阶段不要急着上 Redis、Celery、K8s。

你只需要证明：

```Plain
RAG 链路能跑通
能根据文档回答问题
能返回引用片段
```

---

## Phase 2：加入异步任务

目标：模拟工业项目里的文档入库流程。

### 加入技术

```Plain
Redis
Celery
PostgreSQL
任务状态机
```

### 为什么要加

文档解析、embedding、入库都是耗时任务，不能让用户一直等接口返回。

工业流程应该是：

```Plain
用户上传文档
→ 立即返回 task_id
→ 后台 worker 解析文档
→ 用户查询任务状态
```

任务状态设计：

```Plain
UPLOADED
→ PARSING
→ CHUNKING
→ EMBEDDING
→ INDEXING
→ READY
→ FAILED
```

这一步你就能练到：

```Plain
异步任务
失败重试
任务状态管理
最终一致性
幂等设计
```

---

## Phase 3：拆分服务

目标：从单体项目变成多服务架构。

### 拆成这些服务

```Plain
api-service
rag-service
worker-service
model-service
```

分别负责：

| 服务           | 作用                           |
| -------------- | ------------------------------ |
| api-service    | 用户入口、鉴权、限流、会话管理 |
| rag-service    | 检索、重排、上下文构造         |
| worker-service | 文档解析、切分、embedding 入库 |
| model-service  | 封装 LLM / embedding 调用      |

服务之间通过 HTTP 调用。

例如：

```Plain
api-service 收到用户问题
→ 调用 rag-service 检索文档
→ 调用 model-service 生成答案
→ 返回给用户
```

这一阶段你能练到：

```Plain
服务拆分
服务间通信
接口契约
超时控制
重试机制
```

---

## Phase 4：Docker Compose 本地编排

目标：让项目像真实工业项目一样能一键启动。

### docker-compose 中包含

```Plain
api-service
rag-service
worker-service
model-service
redis
postgres
qdrant
```

启动后：

```Plain
docker compose up
```

整套系统就能跑起来。

这个阶段非常适合写进 README，因为面试官看到会觉得你不是只会 notebook，而是真的懂工程化。

---

## Phase 5：服务治理

目标：让系统从“能跑”变成“稳定”。

### 加入能力

```Plain
timeout
retry
fallback
rate limit
circuit breaker
health check
structured logging
```

具体场景：

| 场景             | 处理方式                          |
| ---------------- | --------------------------------- |
| LLM 超时         | fallback 到备用模型或返回友好提示 |
| embedding 失败   | Celery 自动重试                   |
| 用户频繁请求     | Redis 限流                        |
| rag-service 挂了 | api-service 返回降级信息          |
| 文档重复上传     | 使用 hash 做幂等判断              |
| 向量库写入失败   | 状态设为 FAILED，可重新执行       |

这一步是项目含金量开始变高的地方。

很多学生项目只做到：

```Plain
我能问答
```

你要做到：

```Plain
我知道服务失败时怎么办
```

这就明显更接近工业项目。

---

## Phase 6：可观测性

目标：能定位一次请求到底慢在哪里。

### 加入技术

```Plain
OpenTelemetry
Prometheus
Grafana
结构化日志
trace_id
```

每次问答记录：

```Plain
request_id
user_id
query
retrieved_chunks
retrieval_latency
llm_latency
total_latency
model_name
prompt_tokens
completion_tokens
error_message
```

你可以做一个简单 dashboard：

```Plain
QPS
平均响应时间
错误率
Token 消耗
文档入库成功率
LLM 调用失败率
```

这一步会让你的项目非常像生产系统。

---

## Phase 7：Kubernetes 部署

目标：实践服务注册发现和负载均衡。

### 部署对象

```Plain
Deployment
Service
Ingress
ConfigMap
Secret
HPA
```

你可以先本地用 Minikube / Kind 练。

部署效果：

```Plain
api-service 3 个副本
rag-service 2 个副本
worker-service 2 个副本
model-service 1 个副本
```

然后测试：

```Plain
删除一个 api-service pod
系统是否还能访问？

扩容 rag-service 到 3 个副本
请求是否还能正常负载均衡？

修改配置后滚动更新
服务是否不中断？
```

这一步就覆盖了你一开始提到的：

```Plain
服务注册发现
负载均衡
高可用
规模化部署
```

---

# 七、Agent 能力怎么加？

不要一开始就做复杂 Agent。建议你先做 RAG，然后逐步加 Agent。

## Agent v1：工具选择

给系统加几个工具：

```Plain
search_docs
summarize_paper
compare_documents
generate_markdown_notes
list_documents
get_document_status
```

用户问：

```Plain
帮我总结这篇论文
```

Agent 调用：

```Plain
summarize_paper
```

用户问：

```Plain
对比 ReAct 和 Toolformer
```

Agent 调用：

```Plain
search_docs
compare_documents
```

---

## Agent v2：多步骤工作流

例如：

```Plain
请帮我整理一份 RAG-Fusion 学习笔记
```

Agent 执行：

```Plain
1. 检索 RAG-Fusion 相关资料
2. 提取核心概念
3. 生成流程解释
4. 生成案例
5. 输出 Markdown
```

这就非常贴合你之前让我帮你做 Markdown 笔记的需求。

---

## Agent v3：任务状态化

用 LangGraph 或自己写状态机：

```Plain
START
→ RETRIEVE
→ ANALYZE
→ DRAFT
→ VERIFY
→ OUTPUT
```

这样你就能练：

```Plain
Agent workflow
状态管理
可恢复执行
工具调用链路
```

---

# 八、项目难度控制

为了一个人能做，我建议你这样选择：

## 不建议一开始做

```Plain
多模态图片理解
实时语音
复杂前端
多租户权限系统
真实 GPU 模型部署
Kafka
Istio
复杂服务网格
```

这些先别碰，容易拖垮项目。

## 建议先做

```Plain
PDF / Markdown 文档解析
RAG 问答
异步入库
Docker Compose
Redis 限流
Celery 任务
OpenTelemetry 基础
K8s 简单部署
```

---

# 九、技术选型建议

## 最小可行版本

```Plain
FastAPI
Pydantic
SQLAlchemy
PostgreSQL
Qdrant
OpenAI API 或兼容 API
Celery
Redis
Docker Compose
```

## 为什么用 Qdrant

对个人项目来说，Qdrant 比 Milvus 更轻量，Docker Compose 启动方便，适合学习。

## 为什么用 PostgreSQL

工业项目里关系型数据库非常常见，用它存：

```Plain
用户
文档
任务状态
问答记录
模型调用记录
```

## 为什么用 Celery

Celery 是 Python 生态里非常经典的异步任务框架，适合练工业项目里的 worker 模式。

## 为什么用 FastAPI

FastAPI 是 Python 大模型应用最常见的 API 框架之一，学习收益非常高。

---

# 十、项目目录结构建议

单体阶段：

```Plain
paper-agent-platform/
├── app/
│   ├── main.py
│   ├── api/
│   │   ├── chat.py
│   │   ├── documents.py
│   │   └── health.py
│   ├── core/
│   │   ├── config.py
│   │   ├── logging.py
│   │   └── errors.py
│   ├── schemas/
│   ├── services/
│   │   ├── rag_service.py
│   │   ├── document_service.py
│   │   ├── llm_service.py
│   │   └── agent_service.py
│   ├── repositories/
│   ├── workers/
│   └── utils/
├── data/
├── tests/
├── docker-compose.yml
├── Dockerfile
├── README.md
└── pyproject.toml
```

服务拆分后：

```Plain
paper-agent-platform/
├── services/
│   ├── api-service/
│   ├── rag-service/
│   ├── worker-service/
│   └── model-service/
├── packages/
│   └── common/
├── deploy/
│   ├── docker-compose.yml
│   └── k8s/
├── docs/
└── README.md
```

---

# 十一、你可以写进简历的项目描述

可以这样写：

> 设计并实现一个面向论文与技术文档的 RAG + Agent 智能阅读平台，支持 PDF / Markdown 文档上传、异步解析、向量化入库、基于知识库的问答、论文总结、多文档对比和 Markdown 笔记生成。
>
> 系统采用 FastAPI 构建 API 服务，使用 Celery + Redis 实现文档解析与 embedding 入库的异步任务队列，使用 PostgreSQL 管理文档元数据和任务状态，使用 Qdrant 存储向量索引。
>
> 在工程化方面，项目拆分为 api-service、rag-service、worker-service、model-service，并通过 Docker Compose 进行本地多服务编排；实现 timeout、retry、fallback、Redis 限流、健康检查、结构化日志和 trace_id 链路追踪，提升系统稳定性和可观测性。
>
> 进一步使用 Kubernetes Deployment / Service / Ingress 部署多副本服务，实践服务发现、负载均衡和滚动更新。

这段比“我做了一个 RAG 项目”强很多。

---

# 十二、推荐你最终做到什么程度

你不需要一口气做到满配。按优先级：

## 必做

```Plain
FastAPI RAG 问答
PDF / Markdown 上传
文本切分
embedding 入库
Qdrant 检索
LLM 生成回答
返回引用来源
Celery 异步任务
Redis
PostgreSQL
Docker Compose
```

## 加分

```Plain
Agent 工具选择
多文档对比
Markdown 学习笔记生成
任务状态机
幂等上传
timeout / retry / fallback
结构化日志
trace_id
```

## 高阶加分

```Plain
OpenTelemetry
Prometheus / Grafana
Kubernetes 部署
多副本负载均衡
灰度发布
简单压测
RAG 评测集
```

---

# 十三、最推荐的执行顺序

你可以照这个顺序推进：

```Plain
第 1 步：做 FastAPI + 单文档上传
第 2 步：实现 PDF / Markdown 文本解析
第 3 步：做 chunk 切分
第 4 步：接 embedding 模型
第 5 步：写入 Qdrant
第 6 步：实现 /chat RAG 问答
第 7 步：返回引用片段
第 8 步：引入 PostgreSQL 存文档和任务状态
第 9 步：引入 Celery + Redis 做异步入库
第 10 步：加入任务状态机
第 11 步：实现论文总结 / 对比 / 笔记生成工具
第 12 步：加入简单 Agent 工具选择
第 13 步：Docker Compose 一键启动
第 14 步：加入 timeout / retry / fallback / 限流
第 15 步：加入结构化日志和 trace_id
第 16 步：拆分 api-service / rag-service / worker-service
第 17 步：部署到 K8s
第 18 步：做 README、架构图、接口文档、演示视频
```

---

# 十四、我建议你最终项目不要叫“RAG Demo”

一定不要叫：

```Plain
RAG Demo
个人知识库
PDF 问答系统
```

这些太普通了。

建议叫：

```Plain
PaperPilot
Research Agent Platform
AI Research Assistant
TechDoc Agent
```

中文可以叫：

```Plain
面向论文与技术文档的 RAG + Agent 智能阅读平台
```

这个名字在简历上会更像一个完整项目。

---

# 十五、最终建议

你现在最适合做的不是“机器人全链路项目”，而是：

> **论文 / 技术文档 RAG + Agent 平台，并按照工业化顺序逐步升级。**

它能帮你同时补齐：

```Plain
大模型应用开发
RAG
Agent
异步任务
服务拆分
Docker
K8s
服务治理
数据一致性
可观测性
```

而且数据集好找、实现边界清晰、一个人能完成，最后也非常适合面向大模型应用岗讲项目。
