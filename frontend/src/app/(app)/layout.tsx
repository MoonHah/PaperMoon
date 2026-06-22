import { NavBar } from "@/components/nav-bar";
import { AuthGuard } from "@/components/auth-guard";
import { ToastProvider } from "@/components/ui/toast";

// 应用区（登录后的工作台）：顶部 NavBar + 受 AuthGuard 保护的内容。
// ToastProvider 包裹整个应用区，任意子组件可经 useToast 发通知。
export default function AppLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <ToastProvider>
      <NavBar />
      <main className="flex-1">
        <AuthGuard>{children}</AuthGuard>
      </main>
    </ToastProvider>
  );
}
