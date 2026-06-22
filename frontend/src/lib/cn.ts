// 极简 class 合并：过滤假值后拼接。避免为此引入 clsx 依赖。
export function cn(...classes: Array<string | false | null | undefined>): string {
  return classes.filter(Boolean).join(" ");
}
