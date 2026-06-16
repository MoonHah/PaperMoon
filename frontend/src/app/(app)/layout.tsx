import { NavBar } from "@/components/nav-bar";
import { AuthGuard } from "@/components/auth-guard";

// 应用区（登录后的工作台）：顶部 NavBar + 受 AuthGuard 保护的内容。
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
    </>
  );
}
