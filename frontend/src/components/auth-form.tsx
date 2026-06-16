"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ApiError, loginUser, registerUser } from "@/lib/api";
import { setToken } from "@/lib/auth";

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
        <span className="font-mono text-caption-mono-sm uppercase text-mute">RAG · Agent</span>
      </Link>
      <h1 className="mt-8 text-display-sm">{isLogin ? "登录" : "注册"}</h1>

      <form onSubmit={submit} className="mt-6 space-y-3">
        <input
          type="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="邮箱"
          className="w-full rounded-sm border border-hairline bg-canvas-soft px-4 py-2.5 text-base text-ink placeholder:text-mute focus:border-canvas-mid focus:outline-none"
        />
        <input
          type="password"
          required
          minLength={8}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="密码（至少 8 位）"
          className="w-full rounded-sm border border-hairline bg-canvas-soft px-4 py-2.5 text-base text-ink placeholder:text-mute focus:border-canvas-mid focus:outline-none"
        />
        {error && <p className="text-sm text-danger">{error}</p>}
        <button
          type="submit"
          disabled={busy}
          className="w-full rounded-pill bg-ink px-5 py-2.5 text-sm font-medium text-canvas transition-colors hover:bg-ink/90 disabled:opacity-50"
        >
          {busy ? "处理中…" : isLogin ? "登录" : "注册"}
        </button>
      </form>

      <p className="mt-4 text-sm text-mute">
        {isLogin ? "还没有账号？" : "已有账号？"}
        <Link
          href={isLogin ? "/register" : "/login"}
          className="ml-1 text-ink transition-colors hover:underline"
        >
          {isLogin ? "去注册" : "去登录"}
        </Link>
      </p>
    </div>
  );
}
