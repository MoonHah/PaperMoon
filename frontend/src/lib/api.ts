import { clearToken, getToken } from "./auth";
import type {
  AgentRunRequest,
  AgentRunResponse,
  DocumentChunksResponse,
  DocumentContentResponse,
  DocumentNotesResponse,
  DocumentResponse,
  DocumentStatusResponse,
  DocumentUploadResponse,
  TokenResponse,
  UserResponse,
} from "./types";

const DEFAULT_TIMEOUT_MS = 15_000;
const UPLOAD_TIMEOUT_MS = 60_000; // 上传 + Docling 解析触发，给更长超时
const AGENT_TIMEOUT_MS = 120_000; // Agent 多步推理 + 多次 LLM 调用，给更长超时

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

// 统一 fetch 封装：带超时（AbortController）+ 错误归一化。
async function request<T>(
  path: string,
  init?: RequestInit,
  timeoutMs = DEFAULT_TIMEOUT_MS,
): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  // 注入 Bearer（已登录时）。
  const token = getToken();
  const headers = new Headers(init?.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  try {
    const res = await fetch(path, { ...init, headers, signal: controller.signal });
    if (!res.ok) {
      // 携带 token 仍 401 = token 失效/过期 → 清掉并回登录页（登录请求本身无 token，不触发）。
      if (res.status === 401 && token && typeof window !== "undefined") {
        clearToken();
        window.location.href = "/login";
      }
      let detail = res.statusText;
      try {
        const body = await res.json();
        detail = body.detail ?? body.message ?? detail;
      } catch {
        // 错误体非 JSON，保留 statusText
      }
      throw new ApiError(res.status, detail);
    }
    if (res.status === 204) return undefined as T; // 无内容响应（如 DELETE）
    return (await res.json()) as T;
  } catch (err) {
    if (err instanceof ApiError) throw err;
    if (err instanceof DOMException && err.name === "AbortError") {
      throw new ApiError(408, "请求超时，请稍后重试。");
    }
    throw new ApiError(0, "无法连接服务，请确认后端已启动。");
  } finally {
    clearTimeout(timer);
  }
}

// ── Auth ──

export function registerUser(email: string, password: string): Promise<TokenResponse> {
  return request<TokenResponse>("/api/v1/auth/register", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
}

export function loginUser(email: string, password: string): Promise<TokenResponse> {
  return request<TokenResponse>("/api/v1/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
}

export function getMe(): Promise<UserResponse> {
  return request<UserResponse>("/api/v1/auth/me");
}

export function getDocument(id: string): Promise<DocumentResponse> {
  return request<DocumentResponse>(`/api/v1/documents/${id}`);
}

export function deleteDocument(id: string): Promise<void> {
  return request<void>(`/api/v1/documents/${id}`, { method: "DELETE" });
}

export function listDocuments(): Promise<DocumentResponse[]> {
  // 不带尾斜杠：由 next.config 的显式 rewrite 补成后端要求的 /documents/，
  // 避免 catch-all 丢斜杠后被后端 307 跳到跨域绝对地址。
  return request<DocumentResponse[]>("/api/v1/documents");
}

export function getDocumentStatus(id: string): Promise<DocumentStatusResponse> {
  return request<DocumentStatusResponse>(`/api/v1/documents/${id}/status`);
}

export function getDocumentContent(id: string): Promise<DocumentContentResponse> {
  return request<DocumentContentResponse>(`/api/v1/documents/${id}/content`);
}

export function getDocumentChunks(id: string): Promise<DocumentChunksResponse> {
  return request<DocumentChunksResponse>(`/api/v1/documents/${id}/chunks`);
}

// 拉原件为 blob（带 Bearer）→ 调用方生成 object URL 内嵌。
// <iframe src> 无法携带鉴权头，故不能直接指向 /file，必须先鉴权 fetch 成 blob。
export async function fetchDocumentFile(id: string): Promise<Blob> {
  const token = getToken();
  const headers = new Headers();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const res = await fetch(`/api/v1/documents/${id}/file`, { headers });
  if (!res.ok) {
    if (res.status === 401 && token && typeof window !== "undefined") {
      clearToken();
      window.location.href = "/login";
    }
    throw new ApiError(res.status, "无法加载原件");
  }
  return res.blob();
}

export function generateDocumentNotes(id: string): Promise<DocumentNotesResponse> {
  // 确定性按文档生成笔记（不走 Agent）；含 LLM 调用，给更长超时。
  return request<DocumentNotesResponse>(
    `/api/v1/documents/${id}/notes`,
    { method: "POST" },
    AGENT_TIMEOUT_MS,
  );
}

export function uploadDocument(file: File): Promise<DocumentUploadResponse> {
  const form = new FormData();
  form.append("file", file);
  return request<DocumentUploadResponse>(
    "/api/v1/documents/upload",
    { method: "POST", body: form },
    UPLOAD_TIMEOUT_MS,
  );
}

export function runAgent(req: AgentRunRequest): Promise<AgentRunResponse> {
  return request<AgentRunResponse>(
    "/api/v1/agent/run",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(req),
    },
    AGENT_TIMEOUT_MS,
  );
}
