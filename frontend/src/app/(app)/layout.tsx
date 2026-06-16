import { NavBar } from "@/components/nav-bar";

// 应用区（登录后的工作台）：顶部 NavBar + 内容。
export default function AppLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <>
      <NavBar />
      <main className="flex-1">{children}</main>
    </>
  );
}
