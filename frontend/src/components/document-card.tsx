"use client";

import { useState } from "react";
import Link from "next/link";
import { FileText, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { ApiError, deleteDocument } from "@/lib/api";
import type { DocumentResponse } from "@/lib/types";
import { StatusPill } from "./status-pill";
import { Button } from "@/components/ui/button";

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleString("zh-CN", { hour12: false });
  } catch {
    return iso;
  }
}

export function DocumentCard({
  doc,
  onDeleted,
}: {
  doc: DocumentResponse;
  onDeleted?: (id: string) => void;
}) {
  const [confirming, setConfirming] = useState(false);
  const [deleting, setDeleting] = useState(false);

  // READY 才可点进阅读页；其余状态不跳（正文还没好）。
  const clickable = doc.status === "READY";

  // 卡片是 <Link> 时，删除控件的点击必须阻止默认跳转 + 冒泡。
  function stop(e: React.MouseEvent) {
    e.preventDefault();
    e.stopPropagation();
  }

  async function confirmDelete(e: React.MouseEvent) {
    stop(e);
    setDeleting(true);
    try {
      await deleteDocument(doc.document_id);
      toast.success(`已删除 ${doc.filename}`);
      onDeleted?.(doc.document_id);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "删除失败");
      setDeleting(false);
      setConfirming(false);
    }
  }

  const deleteControl = confirming ? (
    <span className="inline-flex items-center gap-1.5">
      <Button variant="destructive" size="sm" loading={deleting} onClick={confirmDelete}>
        删除
      </Button>
      <Button
        variant="ghost"
        size="sm"
        disabled={deleting}
        onClick={(e) => {
          stop(e);
          setConfirming(false);
        }}
      >
        取消
      </Button>
    </span>
  ) : (
    <button
      type="button"
      aria-label="删除文档"
      onClick={(e) => {
        stop(e);
        setConfirming(true);
      }}
      className="rounded-full p-1.5 text-muted-foreground transition-colors hover:bg-muted hover:text-destructive focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
    >
      <Trash2 className="h-4 w-4" aria-hidden />
    </button>
  );

  const inner = (
    <>
      <div className="flex items-start justify-between gap-4">
        <div className="flex min-w-0 items-start gap-3">
          <FileText className="mt-0.5 h-5 w-5 shrink-0 text-muted-foreground" aria-hidden />
          <div className="min-w-0">
            <p className="truncate text-base text-foreground" title={doc.filename}>
              {doc.filename}
            </p>
            <p className="mt-1 font-mono text-caption-mono-sm uppercase text-muted-foreground">
              {doc.file_type}
              {doc.chunk_count != null ? ` · ${doc.chunk_count} chunks` : ""}
            </p>
          </div>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <StatusPill status={doc.status} />
          {deleteControl}
        </div>
      </div>

      {doc.status === "FAILED" && doc.error_message && (
        <p className="mt-3 rounded-sm bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {doc.error_message}
        </p>
      )}

      <p className="mt-4 text-sm text-muted-foreground">{formatDate(doc.created_at)}</p>
    </>
  );

  if (clickable) {
    return (
      <Link
        href={`/documents/${doc.document_id}`}
        className="block rounded-sm border border-border bg-card p-6 transition-all hover:border-border motion-safe:hover:-translate-y-0.5 motion-safe:hover:shadow-lg"
      >
        {inner}
      </Link>
    );
  }
  return (
    <div className="rounded-sm border border-border bg-card p-6">{inner}</div>
  );
}
