import { cn } from "@/lib/cn";

// 骨架占位：加载态用，比"加载中…"裸字更显精致。motion-safe 尊重 reduced-motion。
export function Skeleton({ className }: { className?: string }) {
  return (
    <div
      aria-hidden
      className={cn("rounded-sm bg-canvas-soft motion-safe:animate-pulse", className)}
    />
  );
}
