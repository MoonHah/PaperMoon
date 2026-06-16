"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, getDocumentStatus, listDocuments } from "@/lib/api";
import {
  TERMINAL_STATUSES,
  type DocumentResponse,
  type DocumentUploadResponse,
} from "@/lib/types";
import { UploadButton } from "@/components/upload-button";
import { DocumentCard } from "@/components/document-card";
import { EmptyState } from "@/components/empty-state";

const POLL_INTERVAL_MS = 2500;
const MAX_POLL_TICKS = 48; // 上限 ≈ 2 分钟：超时仍未落终态则停止轮询，避免对僵尸文档无限请求

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
          <p className="font-mono text-caption-mono uppercase text-mute">Library</p>
          <h1 className="mt-1 text-display-sm">文档库</h1>
        </div>
        <UploadButton onUploaded={handleUploaded} />
      </div>

      <div className="mt-8">
        {docs === null ? (
          <EmptyState title="加载中…" />
        ) : error && docs.length === 0 ? (
          <EmptyState title="加载失败" hint={error} />
        ) : docs.length === 0 ? (
          <EmptyState title="还没有文档" hint="上传一篇 .pdf / .md / .txt 开始" />
        ) : (
          <>
            {pollPaused && docs.some(isPending) && (
              <p className="mb-4 text-sm text-mute">
                状态自动更新已暂停（部分文档长时间未完成），刷新页面可重试。
              </p>
            )}
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              {docs.map((d) => (
                <DocumentCard key={d.document_id} doc={d} />
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
