"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { MessageSquare, PanelLeft, PanelLeftClose, Send, SquarePen } from "lucide-react";
import {
  ApiError,
  deleteConversation,
  getConversation,
  listConversations,
  streamAgent,
} from "@/lib/api";
import type {
  CitedChunk,
  ConversationSummary,
  IntermediateStep,
  MessageOut,
} from "@/lib/types";
import { ToolSteps } from "@/components/tool-steps";
import { CitationCards } from "@/components/citation-card";
import { Markdown } from "@/components/markdown";
import { ChatSidebar } from "@/components/chat-sidebar";
import { ChatScope } from "@/components/chat-scope";
import { ASK_STORAGE_KEY } from "@/components/selection-ask";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";

interface ChatTurn {
  query: string;
  answer: string | null; // null = 等待响应中
  steps: IntermediateStep[];
  citations: CitedChunk[];
  error: string | null;
}

// 历史会话的消息序列 → 成对折叠为 turns（user + 紧随的 assistant）。
function messagesToTurns(messages: MessageOut[]): ChatTurn[] {
  const turns: ChatTurn[] = [];
  for (let i = 0; i < messages.length; i++) {
    if (messages[i].role !== "user") continue;
    const a = messages[i + 1]?.role === "assistant" ? messages[i + 1] : null;
    turns.push({
      query: messages[i].content,
      answer: a?.content ?? null,
      steps: a?.extra?.steps ?? [],
      citations: a?.extra?.citations ?? [],
      error: null,
    });
    if (a) i++;
  }
  return turns;
}

export default function ChatPage() {
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [scopeIds, setScopeIds] = useState<string[]>([]); // 对话文档范围（空=全部）
  const sessionRef = useRef<string | null>(null); // 当前会话 id（langgraph session_id）
  const bottomRef = useRef<HTMLDivElement>(null);

  const refreshList = useCallback(() => {
    listConversations()
      .then(setConversations)
      .catch(() => {});
  }, []);

  useEffect(() => {
    refreshList();
  }, [refreshList]);

  // 划词追问：阅读页选中文字跳来时，sessionStorage 带着选区 → 预填成可直接发送的提问
  useEffect(() => {
    const picked = sessionStorage.getItem(ASK_STORAGE_KEY);
    if (picked) {
      setInput(`请解释这段内容：「${picked}」`);
      sessionStorage.removeItem(ASK_STORAGE_KEY);
    }
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [turns]);

  async function selectConversation(id: string) {
    try {
      const detail = await getConversation(id);
      setTurns(messagesToTurns(detail.messages));
      sessionRef.current = id;
      setActiveId(id);
      setScopeIds([]); // 范围是实时控件，不随历史会话恢复（后端未按会话持久化范围）
    } catch {
      /* 加载失败忽略 */
    }
  }

  function newChat() {
    setTurns([]);
    sessionRef.current = null;
    setActiveId(null);
    setScopeIds([]);
  }

  async function handleDelete(id: string) {
    if (!window.confirm("删除这段对话？")) return;
    try {
      await deleteConversation(id);
      setConversations((prev) => prev.filter((c) => c.conversation_id !== id));
      if (activeId === id) newChat();
    } catch {
      /* 忽略 */
    }
  }

  // 只改最后一个 turn（当前正在进行的这轮）
  function updateLast(mut: (t: ChatTurn) => ChatTurn) {
    setTurns((prev) => {
      const next = [...prev];
      next[next.length - 1] = mut(next[next.length - 1]);
      return next;
    });
  }

  async function send() {
    const query = input.trim();
    if (!query || busy) return;
    setInput("");
    setBusy(true);
    setTurns((prev) => [...prev, { query, answer: null, steps: [], citations: [], error: null }]);

    try {
      await streamAgent(
        {
          user_query: query,
          session_id: sessionRef.current,
          document_ids: scopeIds, // 空数组 = 不限定范围（后端归一为 None）
        },
        (ev) => {
          if (ev.type === "step_start") {
            // 工具发起：先以"运行中"占位，结果回来再更新
            updateLast((t) => ({
              ...t,
              steps: [
                ...t.steps,
                { step: ev.step, action: ev.action, detail: ev.detail, status: "running", result: "" },
              ],
            }));
          } else if (ev.type === "step_result") {
            updateLast((t) => ({
              ...t,
              steps: t.steps.map((s) =>
                s.step === ev.step ? { ...s, status: ev.status, result: ev.result } : s,
              ),
            }));
          } else if (ev.type === "token") {
            // 逐 token 追加：answer 从 null 变为增长中的字符串（打字机效果）
            updateLast((t) => ({ ...t, answer: (t.answer ?? "") + ev.text }));
          } else if (ev.type === "final") {
            if (ev.session_id) {
              sessionRef.current = ev.session_id;
              setActiveId(ev.session_id);
            }
            updateLast((t) => ({ ...t, answer: ev.final_answer, citations: ev.citations ?? [] }));
          } else if (ev.type === "error") {
            updateLast((t) => ({ ...t, answer: null, error: ev.message }));
          }
        },
      );
      refreshList(); // 新建/更新的会话进侧栏（后端已落库）
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "请求失败";
      updateLast((t) => ({ ...t, answer: null, error: msg }));
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
    <div className="flex h-[calc(100vh-56px)]">
      {sidebarOpen && (
        <ChatSidebar
          conversations={conversations}
          activeId={activeId}
          onSelect={selectConversation}
          onNew={newChat}
          onDelete={handleDelete}
        />
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        {/* 顶栏：折叠/展开侧栏 + 新对话 */}
        <div className="flex items-center gap-2 border-b border-border px-4 py-2">
          <Button
            variant="ghost"
            size="icon"
            aria-label={sidebarOpen ? "收起侧栏" : "展开侧栏"}
            onClick={() => setSidebarOpen((o) => !o)}
          >
            {sidebarOpen ? <PanelLeftClose className="h-4 w-4" /> : <PanelLeft className="h-4 w-4" />}
          </Button>
          {!sidebarOpen && (
            <Button variant="ghost" size="sm" onClick={newChat}>
              <SquarePen className="h-4 w-4" aria-hidden />
              新对话
            </Button>
          )}
          <ChatScope selected={scopeIds} onChange={setScopeIds} />
          <span className="ml-auto font-mono text-caption-mono-sm uppercase text-muted-foreground">
            Agent · 对话
          </span>
        </div>

        {/* 消息区 */}
        <div className="flex-1 overflow-y-auto">
          <div className="mx-auto max-w-[860px] px-6 pb-6 pt-6">
            {turns.length === 0 ? (
              <div className="flex flex-col items-center gap-3 py-16 text-center">
                <MessageSquare className="h-8 w-8 text-muted-foreground" aria-hidden />
                <p className="text-base text-foreground">让我们开始对话吧！</p>
              </div>
            ) : (
              <div className="space-y-6">
                {turns.map((t, i) => (
                  <div key={i} className="space-y-3">
                    <div className="flex justify-end">
                      <div className="max-w-[80%] whitespace-pre-wrap rounded-md border border-border bg-muted px-4 py-2.5 text-base">
                        {t.query}
                      </div>
                    </div>
                    <div className="border-l-2 border-primary pl-4">
                      {t.error ? (
                        <>
                          {t.steps.length > 0 && <ToolSteps steps={t.steps} />}
                          <p className="text-destructive">{t.error}</p>
                        </>
                      ) : t.answer === null ? (
                        // 进行中：轨迹实时展开 + 处理指示
                        <>
                          {t.steps.length > 0 && <ToolSteps steps={t.steps} open />}
                          <p className="mt-2 flex items-center gap-2 text-foreground">
                            <span className="h-1.5 w-1.5 rounded-full bg-primary motion-safe:animate-pulse" />
                            {t.steps.length > 0 ? "处理中…" : "思考中…"}
                          </p>
                        </>
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
                ))}
              </div>
            )}
            <div ref={bottomRef} />
          </div>
        </div>

        {/* 输入栏 */}
        <div className="border-t border-border bg-background/90 backdrop-blur">
          <div className="mx-auto flex max-w-[860px] items-end gap-3 px-6 py-4">
            <Textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={onKeyDown}
              rows={1}
              placeholder="有问题，尽管问（Shift + Enter 换行）"
              className="flex-1"
            />
            <Button onClick={send} disabled={!input.trim()} loading={busy} size="lg" aria-label="发送">
              {!busy && <Send className="h-4 w-4" aria-hidden />}
              发送
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
