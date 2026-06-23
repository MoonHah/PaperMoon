import { NavBar } from "@/components/nav-bar";
import { AuthGuard } from "@/components/auth-guard";
import { Toaster } from "@/components/ui/sonner";

// 应用区（登录后的工作台）：顶部 NavBar + 受 AuthGuard 保护的内容 + 全局 sonner 通知。
export default function AppLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <>
      <NavBar />
      <main className="flex-1">
        <AuthGuard>{children}</AuthGuard>
      </main>
      <Toaster />
    </>
  );
}
