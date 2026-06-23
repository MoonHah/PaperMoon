"use client";

import { MessageSquare, Plus, Trash2 } from "lucide-react";
import type { ConversationSummary } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/cn";

export function ChatSidebar({
  conversations,
  activeId,
  onSelect,
  onNew,
  onDelete,
}: {
  conversations: ConversationSummary[];
  activeId: string | null;
  onSelect: (id: string) => void;
  onNew: () => void;
  onDelete: (id: string) => void;
}) {
  return (
    <aside className="flex h-full w-64 shrink-0 flex-col border-r border-border bg-muted/30">
      <div className="p-3">
        <Button variant="outline" className="w-full justify-start" onClick={onNew}>
          <Plus className="h-4 w-4" aria-hidden />
          新对话
        </Button>
      </div>
      <nav className="flex-1 overflow-y-auto px-2 pb-3">
        {conversations.length === 0 ? (
          <p className="px-2 py-4 text-sm text-muted-foreground">还没有历史对话</p>
        ) : (
          <ul className="space-y-0.5">
            {conversations.map((c) => (
              <li key={c.conversation_id}>
                <div
                  className={cn(
                    "group flex items-center gap-1 rounded-md px-2 py-2 text-sm transition-colors",
                    c.conversation_id === activeId
                      ? "bg-background font-medium text-foreground"
                      : "text-muted-foreground hover:bg-background/60 hover:text-foreground",
                  )}
                >
                  <button
                    type="button"
                    onClick={() => onSelect(c.conversation_id)}
                    className="flex min-w-0 flex-1 items-center gap-2 text-left"
                  >
                    <MessageSquare className="h-4 w-4 shrink-0" aria-hidden />
                    <span className="truncate">{c.title}</span>
                  </button>
                  <button
                    type="button"
                    aria-label="删除对话"
                    onClick={() => onDelete(c.conversation_id)}
                    className="shrink-0 rounded p-1 text-muted-foreground opacity-0 transition-opacity hover:text-destructive focus-visible:opacity-100 group-hover:opacity-100"
                  >
                    <Trash2 className="h-3.5 w-3.5" aria-hidden />
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </nav>
    </aside>
  );
}
