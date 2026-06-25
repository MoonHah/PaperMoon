"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { MessageSquarePlus } from "lucide-react";

// 划词追问：在文档工作区选中文字 → 浮出「问 AI」按钮 → 点击把选区写入 sessionStorage 并跳对话页。
// 对话页挂载时读取并预填输入框（见 chat/page.tsx）。
// 仅对可选中的 HTML 文本生效（txt/md 阅读、分块页）；PDF canvas 无文本层 → 无选区 → 按钮不出现，自然降级。
export const ASK_STORAGE_KEY = "papermoon:ask";

export function SelectionAsk() {
  const router = useRouter();
  const [pos, setPos] = useState<{ x: number; y: number } | null>(null);
  const textRef = useRef("");

  useEffect(() => {
    function onMouseUp() {
      const sel = window.getSelection();
      const text = sel?.toString().trim() ?? "";
      if (!text || text.length < 2 || sel!.rangeCount === 0) {
        setPos(null);
        return;
      }
      const rect = sel!.getRangeAt(0).getBoundingClientRect();
      if (rect.width === 0 && rect.height === 0) {
        setPos(null);
        return;
      }
      textRef.current = text;
      setPos({ x: rect.left + rect.width / 2, y: rect.top });
    }
    document.addEventListener("mouseup", onMouseUp);
    return () => document.removeEventListener("mouseup", onMouseUp);
  }, []);

  if (!pos) return null;

  function ask() {
    sessionStorage.setItem(ASK_STORAGE_KEY, textRef.current);
    setPos(null);
    router.push("/chat");
  }

  return (
    <button
      type="button"
      // 用 onMouseDown + preventDefault：在浏览器清除选区/触发 document mouseup 前就执行，避免按钮被提前卸载
      onMouseDown={(e) => {
        e.preventDefault();
        ask();
      }}
      style={{ position: "fixed", left: pos.x, top: pos.y - 44, transform: "translateX(-50%)" }}
      className="z-50 flex items-center gap-1 rounded-md border border-border bg-popover px-3 py-1.5 text-sm font-medium text-foreground shadow-md transition-colors hover:bg-accent"
    >
      <MessageSquarePlus className="h-4 w-4" aria-hidden />
      问 AI
    </button>
  );
}
