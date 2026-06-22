import type { Metadata } from "next";

// server layout：为 /documents 及其子路由提供页面标题（page 是 client 组件）。
export const metadata: Metadata = { title: "文档库" };

export default function DocumentsSectionLayout({ children }: { children: React.ReactNode }) {
  return children;
}
