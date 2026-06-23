import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

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
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="flex min-h-full flex-col bg-background font-sans text-foreground">
        {children}
      </body>
    </html>
  );
}
