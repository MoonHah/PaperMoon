import type { Metadata } from "next";
// 自托管字体：geist 包把 Geist/Geist Mono 的 woff2 打包在本地（next/font/local 机制），
// 不再从 fonts.gstatic.com 下载——国内/离线/无 VPN 均可，避开 next/font/google 拉取失败。
// 其 .variable 默认就是 --font-geist-sans / --font-geist-mono，与 globals.css 一致。
import { GeistSans } from "geist/font/sans";
import { GeistMono } from "geist/font/mono";
import "./globals.css";

export const metadata: Metadata = {
  // 子路由设 title 时自动拼成「对话 · PaperMoon」；无则用 default。
  title: { default: "PaperMoon", template: "%s · PaperMoon" },
  description: "面向论文与技术文档的 RAG + Agent 智能阅读平台",
};

// 根 layout 只负责 html/body/字体；导航与页脚交给 (marketing)/(app) 各自的 layout。
export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="zh-CN"
      className={`${GeistSans.variable} ${GeistMono.variable} h-full antialiased`}
    >
      <body className="flex min-h-full flex-col bg-background font-sans text-foreground">
        {children}
      </body>
    </html>
  );
}
