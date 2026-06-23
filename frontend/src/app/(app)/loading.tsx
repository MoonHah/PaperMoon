import { Loader2 } from "lucide-react";

// 应用区路由切换的即时加载态（段级 Suspense 兜底）。
export default function Loading() {
  return (
    <div
      className="flex min-h-[60vh] items-center justify-center"
      role="status"
      aria-label="加载中"
    >
      <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" aria-hidden />
    </div>
  );
}
