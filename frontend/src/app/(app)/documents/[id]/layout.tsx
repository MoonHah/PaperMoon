"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams, usePathname } from "next/navigation";
import { ArrowLeft, BookOpen, NotebookPen } from "lucide-react";
import { getDocument } from "@/lib/api";
import { Skeleton } from "@/components/ui/skeleton";

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
    { href: `/documents/${id}/read`, label: "阅读", icon: BookOpen },
    { href: `/documents/${id}/notes`, label: "笔记", icon: NotebookPen },
  ];

  return (
    <div className="mx-auto max-w-[760px] px-6 py-8">
      <Link
        href="/documents"
        className="inline-flex items-center gap-1 text-sm text-mute transition-colors hover:text-ink"
      >
        <ArrowLeft className="h-4 w-4" aria-hidden />
        文档库
      </Link>
      {filename === null ? (
        <Skeleton className="mt-4 h-7 w-2/3" />
      ) : (
        <h1 className="mt-4 truncate text-read-heading" title={filename}>
          {filename}
        </h1>
      )}

      <nav className="mt-4 flex gap-1 border-b border-hairline">
        {tabs.map((t) => {
          const active = pathname === t.href;
          const Icon = t.icon;
          return (
            <Link
              key={t.href}
              href={t.href}
              aria-current={active ? "page" : undefined}
              className={`-mb-px inline-flex items-center gap-1.5 border-b-2 px-4 py-2 text-sm transition-colors ${
                active
                  ? "border-accent-breeze font-semibold text-ink"
                  : "border-transparent text-mute hover:text-ink"
              }`}
            >
              <Icon className="h-4 w-4" aria-hidden />
              {t.label}
            </Link>
          );
        })}
      </nav>

      <div className="mt-6">{children}</div>
    </div>
  );
}
