import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

// 统一的 markdown 渲染：阅读 / 笔记 / 对话共用。
// 样式集中在 globals.css 的 .md-content（按设计 token），组件保持极薄。
// remark-gfm 支持表格、删除线、任务列表、自动链接等 GitHub 扩展语法。
export function Markdown({ children }: { children: string }) {
  return (
    <div className="md-content">
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{children}</ReactMarkdown>
    </div>
  );
}
