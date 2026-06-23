import Link from "next/link";

const LINKS = [
  { href: "/documents", label: "文档库" },
  { href: "/chat", label: "对话" },
  { href: "https://github.com", label: "GitHub" },
];

export function Footer() {
  return (
    <footer className="border-t border-border">
      <div className="mx-auto flex max-w-[1200px] flex-col gap-6 px-6 py-12 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-display-xs">PaperMoon</p>
          <p className="mt-1 text-sm text-muted-foreground">
            面向论文与技术文档的 RAG + Agent 阅读平台
          </p>
        </div>
        <ul className="flex gap-6 text-sm text-foreground">
          {LINKS.map((l) => (
            <li key={l.label}>
              <Link href={l.href} className="transition-colors hover:text-foreground">
                {l.label}
              </Link>
            </li>
          ))}
        </ul>
      </div>
    </footer>
  );
}
