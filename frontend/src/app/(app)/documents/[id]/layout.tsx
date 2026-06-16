"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams, usePathname } from "next/navigation";
import { getDocument } from "@/lib/api";

// 文档工作区：返回 + 标题 + 标签页（阅读/笔记），内容由嵌套路由渲染。
export default function DocumentWorkspaceLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const params = useParams<{ id: string }>();
  const id = params.id;
  const pathname = usePathname();
  const [filename, setFilename] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getDocument(id)
      .then((d) => {
        if (!cancelled) setFilename(d.filename);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [id]);

  const tabs = [
    { href: `/documents/${id}/read`, label: "阅读" },
    { href: `/documents/${id}/notes`, label: "笔记" },
  ];

  return (
    <div className="mx-auto max-w-[760px] px-6 py-8">
      <Link href="/documents" className="text-sm text-mute transition-colors hover:text-ink">
        ← 文档库
      </Link>
      <h1 className="mt-4 truncate text-read-heading" title={filename ?? undefined}>
        {filename ?? "…"}
      </h1>

      <nav className="mt-4 flex gap-1 border-b border-hairline">
        {tabs.map((t) => {
          const active = pathname === t.href;
          return (
            <Link
              key={t.href}
              href={t.href}
              className={`-mb-px border-b-2 px-4 py-2 text-sm transition-colors ${
                active
                  ? "border-accent-breeze font-semibold text-ink"
                  : "border-transparent text-mute hover:text-ink"
              }`}
            >
              {t.label}
            </Link>
          );
        })}
      </nav>

      <div className="mt-6">{children}</div>
    </div>
  );
}
