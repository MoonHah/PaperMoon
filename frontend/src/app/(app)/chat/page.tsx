"use client";

import { useEffect, useRef, useState } from "react";
import { MessageSquare, Send, SquarePen } from "lucide-react";
import { ApiError, runAgent } from "@/lib/api";
import type { CitedChunk, IntermediateStep } from "@/lib/types";
import { ToolSteps } from "@/components/tool-steps";
import { CitationCards } from "@/components/citation-card";
import { Markdown } from "@/components/markdown";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";

interface ChatTurn {
  query: string;
  answer: string | null; // null = 等待响应中
  steps: IntermediateStep[];
  citations: CitedChunk[];
  error: string | null;
}

// 对话历史 + session_id 存 sessionStorage：切到文档库/阅读再切回来不丢、刷新也在。
// 后端本就有多轮记忆（langgraph checkpointer + thread_id），前端持久化只为防切页清空。
const CHAT_KEY = "papermoon:chat";

interface ChatState {
  turns: ChatTurn[];
  sessionId: string | null;
}

function persistChat(turns: ChatTurn[], sessionId: string | null) {
  sessionStorage.setItem(CHAT_KEY, JSON.stringify({ turns, sessionId }));
}

export default function ChatPage() {
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  // session_id 用 ref 保存：langgraph 后端会返回，带上即可多轮续聊。
  const sessionRef = useRef<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  // 挂载后从 sessionStorage 恢复（放 effect 里避免 SSR 水合不一致）。
  // 持久化只在「完成」时写（见 send），故存档里不会有 answer===null 的半成品。
  useEffect(() => {
    const raw = sessionStorage.getItem(CHAT_KEY);
    if (!raw) return;
    try {
      const saved = JSON.parse(raw) as ChatState;
      setTurns(saved.turns ?? []);
      sessionRef.current = saved.sessionId ?? null;
    } catch {
      sessionStorage.removeItem(CHAT_KEY);
    }
  }, []);

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
        persistChat(next, sessionRef.current); // write-through：仅在完成态落盘
        return next;
      });
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "请求失败";
      setTurns((prev) => {
        const next = [...prev];
        next[next.length - 1] = { ...next[next.length - 1], answer: null, error: msg };
        persistChat(next, sessionRef.current);
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

  function resetChat() {
    if (busy) return;
    setTurns([]);
    sessionRef.current = null; // 下条消息 session_id=null → 后端开新会话
    sessionStorage.removeItem(CHAT_KEY);
  }

  return (
    <div className="min-h-full">
      <div className="mx-auto max-w-[860px] px-6 pb-32">
        <header className="flex items-end justify-between gap-4 py-6">
          <div>
            <p className="font-mono text-caption-mono uppercase text-muted-foreground">Agent</p>
            <h1 className="mt-1 text-display-sm">对话</h1>
          </div>
          {turns.length > 0 && (
            <Button variant="outline" size="sm" onClick={resetChat} disabled={busy}>
              <SquarePen className="h-3.5 w-3.5" aria-hidden />
              新对话
            </Button>
          )}
        </header>

        <div className="space-y-6">
          {turns.length === 0 ? (
            <div className="flex flex-col items-center gap-3 py-16 text-center">
              <MessageSquare className="h-8 w-8 text-muted-foreground" aria-hidden />
              <p className="text-base text-foreground">让我们开始对话吧！</p>
            </div>
          ) : (
            turns.map((t, i) => (
              <div key={i} className="space-y-3">
                {/* 用户提问 */}
                <div className="flex justify-end">
                  <div className="max-w-[80%] whitespace-pre-wrap rounded-md border border-border bg-muted px-4 py-2.5 text-base">
                    {t.query}
                  </div>
                </div>

                {/* Agent 回答 */}
                <div className="border-l-2 border-primary pl-4">
                  {t.answer === null && !t.error ? (
                    <p className="flex items-center gap-2 text-foreground">
                      <span className="h-1.5 w-1.5 rounded-full bg-primary motion-safe:animate-pulse" />
                      思考中…
                    </p>
                  ) : t.error ? (
                    <p className="text-destructive">{t.error}</p>
                  ) : (
                    <>
                      <div className="text-base text-foreground">
                        <Markdown>{t.answer ?? ""}</Markdown>
                      </div>
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
      <div className="sticky bottom-0 border-t border-border bg-background/90 backdrop-blur">
        <div className="mx-auto max-w-[860px] px-6 py-4">
          <div className="flex items-end gap-3">
            <Textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={onKeyDown}
              rows={1}
              placeholder="问 Agent…（Enter 发送，Shift+Enter 换行）"
              className="flex-1"
            />
            <Button
              onClick={send}
              disabled={!input.trim()}
              loading={busy}
              size="lg"
              aria-label="发送"
            >
              {!busy && <Send className="h-4 w-4" aria-hidden />}
              发送
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
