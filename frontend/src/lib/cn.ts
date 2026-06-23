import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

// shadcn 标准 cn：clsx 条件拼接 + tailwind-merge 处理同类冲突（后者覆盖前者）。
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
