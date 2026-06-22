"use client";

import { forwardRef } from "react";
import { cn } from "@/lib/cn";

const FIELD =
  "w-full rounded-sm border border-hairline bg-canvas-soft px-4 py-2.5 text-base text-ink " +
  "placeholder:text-mute transition-colors " +
  "focus-visible:border-canvas-mid focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-breeze/40";

export const Input = forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(
  function Input({ className, ...rest }, ref) {
    return <input ref={ref} className={cn(FIELD, className)} {...rest} />;
  },
);

export const Textarea = forwardRef<
  HTMLTextAreaElement,
  React.TextareaHTMLAttributes<HTMLTextAreaElement>
>(function Textarea({ className, ...rest }, ref) {
  return <textarea ref={ref} className={cn(FIELD, "resize-none", className)} {...rest} />;
});
