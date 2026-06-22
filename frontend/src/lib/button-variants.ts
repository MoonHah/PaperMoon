import { cn } from "@/lib/cn";

// 纯样式函数（无 "use client"）：server 与 client 组件通用。
// <Button> 在 components/ui/button.tsx，这里只放可被 server 组件（如 not-found）安全调用的类名工具。
export type ButtonVariant = "primary" | "outline" | "ghost" | "danger";
export type ButtonSize = "sm" | "md" | "lg";

const BASE =
  "inline-flex items-center justify-center gap-1.5 rounded-pill font-medium transition-colors " +
  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-breeze focus-visible:ring-offset-2 focus-visible:ring-offset-canvas " +
  "disabled:pointer-events-none disabled:opacity-50";

const VARIANTS: Record<ButtonVariant, string> = {
  primary: "bg-ink text-canvas hover:bg-ink/90",
  outline: "border border-hairline text-body hover:bg-canvas-soft hover:text-ink",
  ghost: "text-body hover:bg-canvas-soft hover:text-ink",
  danger: "border border-danger/40 text-danger hover:bg-danger-soft hover:text-danger",
};

const SIZES: Record<ButtonSize, string> = {
  sm: "px-3 py-1.5 text-sm",
  md: "px-4 py-2 text-sm",
  lg: "px-5 py-2.5 text-sm",
};

export function buttonClasses(variant: ButtonVariant = "primary", size: ButtonSize = "md"): string {
  return cn(BASE, VARIANTS[variant], SIZES[size]);
}
