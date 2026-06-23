"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import { Sparkles } from "lucide-react";
import { ApiError, getDocumentNotes, requestDocumentNotes } from "@/lib/api";
import type { NotesStatus } from "@/lib/types";
import { Markdown } from "@/components/markdown";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";

// 笔记异步生成：进页 GET 状态；点生成→POST→轮询 GET 到 READY/FAILED。
// 结果服务端持久化（{id}.notes.md），切页/刷新/换设备都在；PENDING 可离开稍后回来。
const POLL_MS = 3000;
const MAX_TICKS = 80; // ~4 分钟，覆盖 OpenAI 国内慢（单次可达 1-2 分钟）

export default function NotesTab() {
  const { id } = useParams<{ id: string }>();
  const [status, setStatus] = useState<NotesStatus | null>(null);
  const [notes, setNotes] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pollTimedOut, setPollTimedOut] = useState(false); // PENDING 轮询超时 → 允许重试
  const ticksRef = useRef(0);

  const load = useCallback(async () => {
    const r = await getDocumentNotes(id);
    setStatus(r.status);
    setNotes(r.notes);
    setError(r.error);
  }, [id]);

  useEffect(() => {
    load().catch((e) => setError(e instanceof ApiError ? e.message : "加载失败"));
  }, [load]);

  // PENDING 时轮询，直到 READY/FAILED 或超时（后端 15 分钟兜底，前端 ~4 分钟停轮询）。
  useEffect(() => {
    if (status !== "PENDING") return;
    const timer = setInterval(async () => {
      ticksRef.current += 1;
      if (ticksRef.current > MAX_TICKS) {
        clearInterval(timer);
        setPollTimedOut(true); // 超时仍 PENDING：放出重试入口，避免永久卡死（如 worker 中途挂）
        return;
      }
      try {
        await load();
      } catch {
        /* 单次轮询失败忽略，下次再试 */
      }
    }, POLL_MS);
    return () => clearInterval(timer);
  }, [status, load]);

  async function generate() {
    setError(null);
    ticksRef.current = 0;
    setPollTimedOut(false);
    try {
      const r = await requestDocumentNotes(id);
      setStatus(r.status); // PENDING
      setNotes(null);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "生成失败");
    }
  }

  if (status === null && !error) return <Skeleton className="h-40 w-full rounded-sm" />;

  const pendingStuck = status === "PENDING" && pollTimedOut;
  const showButton =
    status === "NOT_GENERATED" || status === "READY" || status === "FAILED" || pendingStuck;
  const buttonLabel =
    status === "READY" ? "重新生成" : status === "NOT_GENERATED" ? "生成学习笔记" : "重试";

  return (
    <div>
      {showButton && (
        <Button type="button" onClick={generate}>
          <Sparkles className="h-4 w-4" aria-hidden />
          {buttonLabel}
        </Button>
      )}

      {status === "PENDING" && !pollTimedOut && (
        <p className="flex items-center gap-2 text-sm text-muted-foreground">
          <span className="h-1.5 w-1.5 rounded-full bg-info motion-safe:animate-pulse" />
          正在生成笔记…（模型较慢时可能需要一两分钟，可离开本页，稍后回来查看）
        </p>
      )}

      {pendingStuck && (
        <p className="mt-3 text-sm text-muted-foreground">生成耗时过长或被中断，可点上方「重试」。</p>
      )}

      {error && <p className="mt-3 text-sm text-destructive">{error}</p>}

      {status === "READY" && notes && (
        <article className="mt-4 rounded-sm bg-card p-8 text-read-body text-foreground">
          <Markdown>{notes}</Markdown>
        </article>
      )}
    </div>
  );
}
