"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ApiError, loginUser, registerUser } from "@/lib/api";
import { setToken } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export function AuthForm({ mode }: { mode: "login" | "register" }) {
  const router = useRouter();
  const isLogin = mode === "login";
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      const res = isLogin
        ? await loginUser(email, password)
        : await registerUser(email, password);
      setToken(res.access_token);
      router.push("/documents");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "操作失败");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto flex min-h-[70vh] max-w-sm flex-col justify-center px-6">
      <Link href="/" className="flex items-baseline gap-2">
        <span className="text-display-xs">PaperMoon</span>
        <span className="font-mono text-caption-mono-sm uppercase text-muted-foreground">RAG · Agent</span>
      </Link>
      <h1 className="mt-8 text-display-sm">{isLogin ? "登录" : "注册"}</h1>

      <form onSubmit={submit} className="mt-6 space-y-3">
        <Input
          type="email"
          required
          autoFocus
          autoComplete="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="邮箱"
        />
        <Input
          type="password"
          required
          minLength={8}
          autoComplete={isLogin ? "current-password" : "new-password"}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="密码（≥8 位，含字母和数字）"
        />
        {!isLogin && !error && (
          <p className="text-sm text-muted-foreground">至少 8 位，需同时包含字母和数字。</p>
        )}
        {error && <p className="text-sm text-destructive">{error}</p>}
        <Button type="submit" size="lg" loading={busy} className="w-full">
          {isLogin ? "登录" : "注册"}
        </Button>
      </form>

      <p className="mt-4 text-sm text-muted-foreground">
        {isLogin ? "还没有账号？" : "已有账号？"}
        <Link
          href={isLogin ? "/register" : "/login"}
          className="ml-1 text-foreground transition-colors hover:underline"
        >
          {isLogin ? "去注册" : "去登录"}
        </Link>
      </p>
    </div>
  );
}
