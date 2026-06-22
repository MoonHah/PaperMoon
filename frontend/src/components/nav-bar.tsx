"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Library, LogOut, MessageSquare, type LucideIcon } from "lucide-react";
import { getMe } from "@/lib/api";
import { clearToken, getToken } from "@/lib/auth";
import { Button, buttonClasses } from "@/components/ui/button";

type NavLink = { href: string; label: string; icon: LucideIcon; disabled?: boolean };

const LINKS: NavLink[] = [
  { href: "/documents", label: "文档库", icon: Library },
  { href: "/chat", label: "对话", icon: MessageSquare },
];

export function NavBar() {
  const pathname = usePathname();
  const [email, setEmail] = useState<string | null>(null);

  useEffect(() => {
    if (getToken()) {
      getMe()
        .then((u) => setEmail(u.email))
        .catch(() => {});
    }
  }, []);

  function logout() {
    clearToken();
    window.location.href = "/login";
  }

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
                    aria-current={pathname.startsWith(l.href) ? "page" : undefined}
                    className={`inline-flex items-center gap-1.5 rounded-pill px-4 py-1.5 text-sm transition-colors ${
                      pathname.startsWith(l.href)
                        ? "bg-canvas-soft font-semibold text-ink"
                        : "text-body hover:text-ink"
                    }`}
                  >
                    <l.icon className="h-4 w-4" aria-hidden />
                    {l.label}
                  </Link>
                </li>
              ),
            )}
          </ul>

          {/* 账户区：已登录显邮箱 + 退出，未登录显登录链接 */}
          {email ? (
            <div className="flex items-center gap-2">
              <span className="hidden max-w-[160px] truncate text-sm text-mute sm:inline" title={email}>
                {email}
              </span>
              <Button type="button" variant="outline" size="sm" onClick={logout}>
                <LogOut className="h-3.5 w-3.5" aria-hidden />
                <span className="hidden sm:inline">退出</span>
              </Button>
            </div>
          ) : (
            <Link href="/login" className={buttonClasses("outline", "sm")}>
              登录
            </Link>
          )}
        </div>
      </nav>
    </header>
  );
}
