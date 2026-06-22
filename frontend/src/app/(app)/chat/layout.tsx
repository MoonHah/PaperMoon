import type { Metadata } from "next";

// server layout：仅为 /chat 提供页面标题（page.tsx 是 client 组件，无法自带 metadata）。
export const metadata: Metadata = { title: "对话" };

export default function ChatLayout({ children }: { children: React.ReactNode }) {
  return children;
}
