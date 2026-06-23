"use client";

import { useEffect } from "react";
import { Button } from "@/components/ui/button";

// 应用区错误边界：渲染期未捕获异常 → 友好兜底 + 重试（reset 重新挂载该段）。
export default function AppError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <div className="mx-auto flex min-h-[60vh] max-w-md flex-col items-center justify-center gap-4 px-6 text-center">
      <p className="font-mono text-caption-mono uppercase text-muted-foreground">Error</p>
      <h1 className="text-display-xs">出错了</h1>
      <p className="text-sm text-muted-foreground">页面遇到意外错误，可以重试或刷新页面。</p>
      <Button onClick={reset}>重试</Button>
    </div>
  );
}
