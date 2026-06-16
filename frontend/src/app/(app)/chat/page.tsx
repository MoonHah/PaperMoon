"use client";

import { useEffect, useRef, useState } from "react";
import { ApiError, runAgent } from "@/lib/api";
import type { CitedChunk, IntermediateStep } from "@/lib/types";
import { ToolSteps } from "@/components/tool-steps";
import { CitationCards } from "@/components/citation-card";

interface ChatTurn {
  query: string;
  answer: string | null; // null = 等待响应中
  steps: IntermediateStep[];
  citations: CitedChunk[];
  error: string | null;
}

export default function ChatPage() {
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  // session_id 用 ref 保存：langgraph 后端会返回，带上即可多轮续聊；
  // handwritten 后端返回 null，则每轮独立（无记忆）。页面对两者都兼容。
  const sessionRef = useRef<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [turns]);

  async function send() {
    const query = input.trim();
    if (!query || busy) return;
    setInput("");
    setBusy(true);
    setTurns((prev) => [
      ...prev,
      { query, answer: null, steps: [], citations: [], error: null },
    ]);

    try {
      const res = await runAgent({ user_query: query, session_id: sessionRef.current });
      if (res.session_id) sessionRef.current = res.session_id;
      setTurns((prev) => {
        const next = [...prev];
        next[next.length - 1] = {
          query,
          answer: res.final_answer,
          steps: res.intermediate_steps,
          citations: res.citations,
          error: res.error,
        };
        return next;
      });
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "请求失败";
      setTurns((prev) => {
        const next = [...prev];
        next[next.length - 1] = { ...next[next.length - 1], answer: null, error: msg };
        return next;
      });
    } finally {
      setBusy(false);
    }
  }

  function onKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  }

  return (
    <div className="min-h-full">
      <div className="mx-auto max-w-[860px] px-6 pb-32">
        <header className="py-6">
          <p className="font-mono text-caption-mono uppercase text-mute">Agent</p>
          <h1 className="mt-1 text-display-sm">对话</h1>
        </header>

        <div className="space-y-6">
          {turns.length === 0 ? (
            <p className="text-mute">
              问点什么——Agent 会自动选工具、多步推理（ReAct），按需检索、总结、对比或生成笔记，并给出引用。
            </p>
          ) : (
            turns.map((t, i) => (
              <div key={i} className="space-y-3">
                {/* 用户提问 */}
                <div className="flex justify-end">
                  <div className="max-w-[80%] whitespace-pre-wrap rounded-md border border-hairline bg-canvas-soft px-4 py-2.5 text-base">
                    {t.query}
                  </div>
                </div>

                {/* Agent 回答 */}
                <div className="border-l-2 border-accent-breeze pl-4">
                  {t.answer === null && !t.error ? (
                    <p className="flex items-center gap-2 text-body">
                      <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-accent-breeze" />
                      思考中…
                    </p>
                  ) : t.error ? (
                    <p className="text-danger">{t.error}</p>
                  ) : (
                    <>
                      <p className="whitespace-pre-wrap text-base text-body">{t.answer}</p>
                      <ToolSteps steps={t.steps} />
                      <CitationCards citations={t.citations} />
                    </>
                  )}
                </div>
              </div>
            ))
          )}
          <div ref={bottomRef} />
        </div>
      </div>

      {/* 输入栏：sticky 贴底，随窗口滚动常驻 */}
      <div className="sticky bottom-0 border-t border-hairline bg-canvas/90 backdrop-blur">
        <div className="mx-auto max-w-[860px] px-6 py-4">
          <div className="flex items-end gap-3">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={onKeyDown}
              rows={1}
              placeholder="问 Agent…（Enter 发送，Shift+Enter 换行）"
              className="flex-1 resize-none rounded-sm border border-hairline bg-canvas-soft px-4 py-2.5 text-base text-ink placeholder:text-mute focus:border-canvas-mid focus:outline-none"
            />
            <button
              type="button"
              onClick={send}
              disabled={busy || !input.trim()}
              className="rounded-pill bg-ink px-5 py-2.5 text-sm font-medium text-canvas transition-colors hover:bg-ink/90 disabled:opacity-50"
            >
              发送
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
