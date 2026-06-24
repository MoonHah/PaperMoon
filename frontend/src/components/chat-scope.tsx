"use client";

import { useEffect, useRef, useState } from "react";
import { Check, ChevronDown, FileText } from "lucide-react";
import { listDocuments } from "@/lib/api";
import type { DocumentResponse } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/cn";

// 对话文档范围选择器：勾选若干已就绪文档把检索/列举限定其中；不选 = 全部已就绪文档。
// 选中的 id 由父组件持有并随 runAgent 作为 document_ids 透传到后端。
export function ChatScope({
  selected,
  onChange,
}: {
  selected: string[];
  onChange: (ids: string[]) => void;
}) {
  const [docs, setDocs] = useState<DocumentResponse[]>([]);
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    listDocuments()
      .then((all) => setDocs(all.filter((d) => d.status === "READY")))
      .catch(() => {});
  }, []);

  // 点击面板外部关闭
  useEffect(() => {
    function onDocClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onDocClick);
    return () => document.removeEventListener("mousedown", onDocClick);
  }, []);

  function toggle(id: string) {
    onChange(selected.includes(id) ? selected.filter((x) => x !== id) : [...selected, id]);
  }

  const label = selected.length === 0 ? "全部文档" : `${selected.length} 篇`;

  return (
    <div className="relative" ref={ref}>
      <Button variant="ghost" size="sm" onClick={() => setOpen((o) => !o)}>
        <FileText className="h-4 w-4" aria-hidden />
        范围：{label}
        <ChevronDown className="h-3.5 w-3.5" aria-hidden />
      </Button>
      {open && (
        <div className="absolute left-0 z-20 mt-1 max-h-72 w-72 overflow-y-auto rounded-md border border-border bg-popover p-1 shadow-md">
          <button
            type="button"
            onClick={() => onChange([])}
            className={cn(
              "flex w-full items-center gap-2 rounded-sm px-3 py-2 text-left text-sm hover:bg-accent",
              selected.length === 0 ? "font-medium text-foreground" : "text-muted-foreground",
            )}
          >
            <span className="flex-1">全部文档</span>
            {selected.length === 0 && <Check className="h-4 w-4" aria-hidden />}
          </button>
          {docs.length === 0 ? (
            <p className="px-3 py-2 text-sm text-muted-foreground">没有已就绪文档</p>
          ) : (
            docs.map((d) => {
              const on = selected.includes(d.document_id);
              return (
                <button
                  key={d.document_id}
                  type="button"
                  onClick={() => toggle(d.document_id)}
                  className={cn(
                    "flex w-full items-center gap-2 rounded-sm px-3 py-2 text-left text-sm hover:bg-accent",
                    on ? "font-medium text-foreground" : "text-muted-foreground",
                  )}
                >
                  <span className="min-w-0 flex-1 truncate">{d.filename}</span>
                  {on && <Check className="h-4 w-4 shrink-0" aria-hidden />}
                </button>
              );
            })
          )}
        </div>
      )}
    </div>
  );
}
