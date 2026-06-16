"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

type NavLink = { href: string; label: string; disabled?: boolean };

const LINKS: NavLink[] = [
  { href: "/documents", label: "文档库" },
  { href: "/chat", label: "对话" },
];

export function NavBar() {
  const pathname = usePathname();

  return (
    <header className="sticky top-0 z-10 border-b border-hairline bg-canvas/80 backdrop-blur">
      <nav className="mx-auto flex max-w-[1200px] items-center justify-between px-6 py-3">
        <Link href="/documents" className="flex items-baseline gap-2">
          <span className="text-display-xs">PaperMoon</span>
          <span className="font-mono text-caption-mono-sm uppercase text-mute">
            RAG · Agent
          </span>
        </Link>

        <div className="flex items-center gap-3">
          <ul className="flex items-center gap-1">
            {LINKS.map((l) =>
              l.disabled ? (
                <li key={l.href}>
                  <span className="cursor-not-allowed rounded-pill px-4 py-1.5 text-sm text-mute/60">
                    {l.label}
                    <span className="ml-1.5 font-mono text-[10px] uppercase">soon</span>
                  </span>
                </li>
              ) : (
                <li key={l.href}>
                  <Link
                    href={l.href}
                    className={`rounded-pill px-4 py-1.5 text-sm transition-colors ${
                      pathname.startsWith(l.href)
                        ? "bg-canvas-soft font-semibold text-ink"
                        : "text-body hover:text-ink"
                    }`}
                  >
                    {l.label}
                  </Link>
                </li>
              ),
            )}
          </ul>

          {/* 账户占位：P2 接真实登录前为静态占位 */}
          <span
            className="cursor-not-allowed rounded-pill border border-hairline px-4 py-1.5 text-sm text-mute"
            title="登录功能即将上线"
          >
            登录
          </span>
        </div>
      </nav>
    </header>
  );
}
