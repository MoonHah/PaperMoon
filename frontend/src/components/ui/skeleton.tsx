import { cn } from "@/lib/cn";

// 骨架占位（shadcn 版）。motion-safe 尊重 prefers-reduced-motion。
function Skeleton({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="skeleton"
      className={cn("rounded-md bg-muted motion-safe:animate-pulse", className)}
      {...props}
    />
  );
}

export { Skeleton };
