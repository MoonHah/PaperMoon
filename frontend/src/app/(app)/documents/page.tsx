"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { AlertCircle, Inbox, RefreshCw } from "lucide-react";
import { ApiError, getDocumentStatus, listDocuments } from "@/lib/api";
import {
  TERMINAL_STATUSES,
  type DocumentResponse,
  type DocumentUploadResponse,
} from "@/lib/types";
import { UploadButton } from "@/components/upload-button";
import { DocumentCard } from "@/components/document-card";
import { EmptyState } from "@/components/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";

const POLL_INTERVAL_MS = 2500;
// 上限 ≈ 6 分钟：需覆盖大 PDF 的 OCR 解析（可达数分钟），否则会在解析途中误判为卡住。
// 仍设上限：worker 真挂时不无限请求；超时后用户可手动「刷新」续查（后端 15 分钟对账兜底置 FAILED）。
const MAX_POLL_TICKS = 144;

function isPending(d: DocumentResponse): boolean {
  return !TERMINAL_STATUSES.includes(d.status);
}

export default function DocumentsPage() {
  const [docs, setDocs] = useState<DocumentResponse[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pollPaused, setPollPaused] = useState(false);
  const pollTicksRef = useRef(0); // 跨 effect 重建持续累计 tick 数

  const load = useCallback(async () => {
    try {
      const list = await listDocuments();
      setDocs(list);
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "加载失败");
      setDocs([]);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  // 轮询：只要存在非终态文档，定时刷新它们的状态，直到全部 READY/FAILED。
  // 加 MAX_POLL_TICKS 上限护栏：被中断的僵尸文档可能永远非终态，不能无限轮询。
  useEffect(() => {
    if (!docs || pollPaused) return;
    const pending = docs.filter(isPending);
    if (pending.length === 0) return;

    const timer = setInterval(async () => {
      pollTicksRef.current += 1;
      if (pollTicksRef.current > MAX_POLL_TICKS) {
        clearInterval(timer);
        setPollPaused(true);
        return;
      }
      const updates = await Promise.all(
        pending.map((d) =>
          getDocumentStatus(d.document_id).catch(() => null),
        ),
      );
      setDocs((prev) =>
        prev
          ? prev.map((d) => {
              const u = updates.find((x) => x?.document_id === d.document_id);
              return u
                ? {
                    ...d,
                    status: u.status,
                    chunk_count: u.chunk_count,
                    error_message: u.error_message,
                  }
                : d;
            })
          : prev,
      );
    }, POLL_INTERVAL_MS);

    return () => clearInterval(timer);
  }, [docs, pollPaused]);

  function handleDeleted(id: string) {
    setDocs((prev) => (prev ? prev.filter((d) => d.document_id !== id) : prev));
  }

  // 手动刷新：重置轮询计数/暂停态并重新拉取（暂停后续查、或随时主动刷新）。
  function refresh() {
    pollTicksRef.current = 0;
    setPollPaused(false);
    load();
  }

  function handleUploaded(doc: DocumentUploadResponse) {
    // 新上传：重置轮询计数与暂停态，让新文档能被轮询到终态。
    pollTicksRef.current = 0;
    setPollPaused(false);
    // 乐观插入：用上传响应构造临时记录，轮询会补全 chunk_count 等字段。
    setDocs((prev) => [
      {
        document_id: doc.document_id,
        filename: doc.filename,
        file_type: doc.filename.split(".").pop()?.toUpperCase() ?? "?",
        status: doc.status,
        chunk_count: null,
        error_message: null,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      },
      ...(prev ?? []),
    ]);
  }

  return (
    <div className="mx-auto max-w-[1200px] px-6 py-10">
      <div className="flex items-end justify-between gap-4">
        <div>
          <p className="font-mono text-caption-mono uppercase text-muted-foreground">Library</p>
          <h1 className="mt-1 text-display-sm">文档库</h1>
        </div>
        <div className="flex items-end gap-3">
          <Button variant="outline" size="sm" onClick={refresh}>
            <RefreshCw className="h-4 w-4" aria-hidden />
            刷新
          </Button>
          <UploadButton onUploaded={handleUploaded} />
        </div>
      </div>

      <div className="mt-8">
        {docs === null ? (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="rounded-sm border border-border bg-card p-6">
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0 flex-1 space-y-2">
                    <Skeleton className="h-4 w-3/4" />
                    <Skeleton className="h-3 w-1/3" />
                  </div>
                  <Skeleton className="h-5 w-16 rounded-full" />
                </div>
                <Skeleton className="mt-6 h-3 w-1/2" />
              </div>
            ))}
          </div>
        ) : error && docs.length === 0 ? (
          <EmptyState icon={AlertCircle} title="加载失败" hint={error} />
        ) : docs.length === 0 ? (
          <EmptyState
            icon={Inbox}
            title="还没有文档"
            hint="上传一篇 .pdf / .md / .txt 开始你的阅读与对话"
            action={<UploadButton onUploaded={handleUploaded} />}
          />
        ) : (
          <>
            {pollPaused && docs.some(isPending) && (
              <p className="mb-4 text-sm text-muted-foreground">
                状态自动更新已暂停（部分文档处理较久）。点右上角「刷新」继续查看进度。
              </p>
            )}
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              {docs.map((d) => (
                <DocumentCard key={d.document_id} doc={d} onDeleted={handleDeleted} />
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
