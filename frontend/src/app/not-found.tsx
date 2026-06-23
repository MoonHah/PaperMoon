import Link from "next/link";
import { buttonVariants } from "@/components/ui/button";

// 全局 404（用根 layout 渲染，故 server 组件里用纯 buttonClasses 而非 <Button>）。
export default function NotFound() {
  return (
    <div className="mx-auto flex min-h-[70vh] max-w-md flex-col items-center justify-center gap-4 px-6 text-center">
      <p className="font-mono text-caption-mono uppercase text-muted-foreground">404</p>
      <h1 className="text-display-xs">页面不存在</h1>
      <p className="text-sm text-muted-foreground">你访问的页面不存在或已被移动。</p>
      <Link href="/documents" className={buttonVariants({ variant: "outline" })}>
        回到文档库
      </Link>
    </div>
  );
}
