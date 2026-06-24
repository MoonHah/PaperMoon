// 流式端点专用 Route Handler。
// 起因：next.config 的 rewrites 代理会缓冲 SSE（前端表现为"整段弹出"，非逐 token）。
// 改用 Route Handler 直通后端响应体（ReadableStream）——文件路由优先于 afterFiles rewrites，
// 故仅此路径走这里、其余 /api/* 仍走 rewrites；既绕开缓冲又保持同源、无需 CORS。
export const dynamic = "force-dynamic"; // 禁缓存，保证逐 chunk 实时下发

const BACKEND_URL = process.env.BACKEND_URL ?? "http://localhost:8008";

export async function POST(request: Request) {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  const auth = request.headers.get("authorization");
  if (auth) headers.Authorization = auth; // 透传 Bearer

  const upstream = await fetch(`${BACKEND_URL}/api/v1/agent/run/stream`, {
    method: "POST",
    headers,
    body: await request.text(),
  });

  // 直通后端的 ReadableStream → 逐 chunk 流给浏览器，不在代理层缓冲
  return new Response(upstream.body, {
    status: upstream.status,
    headers: {
      "Content-Type": "text/event-stream; charset=utf-8",
      "Cache-Control": "no-cache, no-transform",
      "X-Accel-Buffering": "no",
    },
  });
}
