// 对齐后端 Pydantic schema（app/schemas/document.py）。

export type DocStatus =
  | "UPLOADED"
  | "PARSING"
  | "CHUNKING"
  | "EMBEDDING"
  | "INDEXING"
  | "READY"
  | "FAILED";

export interface DocumentResponse {
  document_id: string;
  filename: string;
  file_type: string;
  status: DocStatus;
  chunk_count: number | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
}

export interface DocumentUploadResponse {
  document_id: string;
  filename: string;
  task_id: string;
  status: DocStatus;
}

export interface DocumentStatusResponse {
  document_id: string;
  task_id: string | null;
  status: DocStatus;
  chunk_count: number | null;
  error_message: string | null;
}

export interface DocumentContentResponse {
  document_id: string;
  filename: string;
  content: string;
}

export interface DocumentNotesResponse {
  document_id: string;
  filename: string;
  notes: string;
}

// 处理已结束的终态：轮询到这两个状态即可停止。
export const TERMINAL_STATUSES: DocStatus[] = ["READY", "FAILED"];

// ── Auth ──

export interface TokenResponse {
  access_token: string;
  token_type: string;
}

export interface UserResponse {
  id: string;
  email: string;
}

// ── Agent（对齐 app/agent/schemas.py）──

export interface IntermediateStep {
  step: number;
  action: string;
  detail: string;
  status: string;
}

export interface CitedChunk {
  text: string;
  document_id: string;
  filename: string;
}

export interface AgentRunRequest {
  user_query: string;
  document_ids?: string[];
  session_id?: string | null;
}

export interface AgentRunResponse {
  final_answer: string;
  selected_tool: string;
  intermediate_steps: IntermediateStep[];
  citations: CitedChunk[];
  error: string | null;
  session_id: string | null;
}
