import Link from "next/link";
import type { DocumentResponse } from "@/lib/types";
import { StatusPill } from "./status-pill";

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleString("zh-CN", { hour12: false });
  } catch {
    return iso;
  }
}

export function DocumentCard({ doc }: { doc: DocumentResponse }) {
  // READY 才可点进阅读页；其余状态不跳（正文还没好）。
  const clickable = doc.status === "READY";
  const inner = (
    <>
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <p className="truncate text-base text-ink" title={doc.filename}>
            {doc.filename}
          </p>
          <p className="mt-1 font-mono text-caption-mono-sm uppercase text-mute">
            {doc.file_type}
            {doc.chunk_count != null ? ` · ${doc.chunk_count} chunks` : ""}
          </p>
        </div>
        <StatusPill status={doc.status} />
      </div>

      {doc.status === "FAILED" && doc.error_message && (
        <p className="mt-3 rounded-sm bg-danger-soft px-3 py-2 text-sm text-danger">
          {doc.error_message}
        </p>
      )}

      <p className="mt-4 text-sm text-mute">{formatDate(doc.created_at)}</p>
    </>
  );

  if (clickable) {
    return (
      <Link
        href={`/documents/${doc.document_id}`}
        className="block rounded-sm border border-hairline bg-canvas-card p-6 transition-colors hover:border-canvas-mid"
      >
        {inner}
      </Link>
    );
  }
  return (
    <div className="rounded-sm border border-hairline bg-canvas-card p-6">{inner}</div>
  );
}
