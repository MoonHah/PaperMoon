import { MarketingNav } from "@/components/marketing-nav";
import { Footer } from "@/components/footer";

// 营销区（公开落地页）：营销顶栏 + 内容 + 页脚。
export default function MarketingLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <>
      <MarketingNav />
      <main className="flex-1">{children}</main>
      <Footer />
    </>
  );
}
