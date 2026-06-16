import Link from "next/link";

const CAPABILITIES = [
  {
    tag: "RETRIEVAL",
    title: "多策略检索 + 重排",
    desc: "Simple / Multi-Query / HyDE 可插拔检索，再叠加 LLM 重排精排，召回更准。",
  },
  {
    tag: "AGENT",
    title: "Agent 多步推理",
    desc: "function calling 选工具 + ReAct 循环，自动按需检索、总结、对比、生成笔记。",
  },
  {
    tag: "MEMORY",
    title: "多轮对话记忆",
    desc: "LangGraph checkpointer 持久化会话，记得上文，能解析「它 / 那两篇」等指代。",
  },
  {
    tag: "PARSING",
    title: "Docling 高精度解析",
    desc: "PDF 多栏排版、表格、公式结构化为 Markdown，比平铺文本有更高的 chunk 质量。",
  },
];

const TOOLS = [
  ["search_documents", "检索文档片段，回答具体问题"],
  ["summarize_document", "总结某一篇完整文档"],
  ["compare_documents", "对比两篇或多篇文档的异同"],
  ["generate_markdown_notes", "生成结构化 Markdown 学习笔记"],
  ["list_documents", "列出可用文档，解析自然语言指代"],
];

export default function LandingPage() {
  return (
    <>
      {/* Hero */}
      <section className="mx-auto max-w-[1200px] px-6 py-24 sm:py-32">
        <p className="font-mono text-caption-mono uppercase text-mute">
          RAG · AGENT · 阅读平台
        </p>
        <h1 className="mt-4 max-w-3xl text-display-md md:text-display-xl">
          把论文读薄
        </h1>
        <p className="mt-6 max-w-xl text-lg text-body">
          上传论文与技术文档，PaperMoon 用检索增强 + 多步 Agent 帮你检索、总结、对比、做笔记，并支持多轮追问。
        </p>
        <div className="mt-8 flex flex-wrap gap-3">
          <Link
            href="/documents"
            className="rounded-pill bg-ink px-5 py-2.5 text-sm font-medium text-canvas transition-colors hover:bg-ink/90"
          >
            进入应用
          </Link>
          <Link
            href="/chat"
            className="rounded-pill border border-hairline px-5 py-2.5 text-sm text-ink transition-colors hover:bg-canvas-soft"
          >
            试试对话
          </Link>
        </div>
      </section>

      <div className="border-t border-hairline" />

      {/* 能力区 */}
      <section className="mx-auto max-w-[1200px] px-6 py-20">
        <p className="font-mono text-caption-mono uppercase text-mute">能力</p>
        <h2 className="mt-2 text-display-md">不止是搜索，是读懂</h2>
        <div className="mt-10 grid grid-cols-1 gap-4 sm:grid-cols-2">
          {CAPABILITIES.map((c) => (
            <div
              key={c.tag}
              className="rounded-sm border border-hairline bg-canvas-card p-6"
            >
              <p className="font-mono text-caption-mono-sm uppercase text-mute">
                {c.tag}
              </p>
              <h3 className="mt-2 text-display-xs">{c.title}</h3>
              <p className="mt-2 text-base text-body">{c.desc}</p>
            </div>
          ))}
        </div>
      </section>

      <div className="border-t border-hairline" />

      {/* 工具展示 */}
      <section className="mx-auto max-w-[1200px] px-6 py-20">
        <p className="font-mono text-caption-mono uppercase text-mute">Agent 工具</p>
        <h2 className="mt-2 text-display-md">五个工具，自主编排</h2>
        <ul className="mt-10 divide-y divide-hairline border-y border-hairline">
          {TOOLS.map(([name, desc]) => (
            <li key={name} className="flex flex-col gap-1 py-4 sm:flex-row sm:items-baseline sm:gap-6">
              <span className="font-mono text-sm uppercase text-ink sm:w-72">
                {name}
              </span>
              <span className="text-base text-body">{desc}</span>
            </li>
          ))}
        </ul>
      </section>
    </>
  );
}
