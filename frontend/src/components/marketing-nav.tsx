import Link from "next/link";

// 营销页顶栏：logo + 「进入应用」CTA（区别于应用区 NavBar 的功能标签）。
export function MarketingNav() {
  return (
    <header className="border-b border-border">
      <nav className="mx-auto flex max-w-[1200px] items-center justify-between px-6 py-4">
        <Link href="/" className="flex items-baseline gap-2">
          <span className="text-display-xs">PaperMoon</span>
          <span className="font-mono text-caption-mono-sm uppercase text-muted-foreground">
            RAG · Agent
          </span>
        </Link>
        <Link
          href="/documents"
          className="rounded-full bg-primary px-4 py-1.5 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
        >
          进入应用
        </Link>
      </nav>
    </header>
  );
}
