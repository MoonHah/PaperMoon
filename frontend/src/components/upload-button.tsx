"use client";

import { useRef, useState } from "react";
import { Upload } from "lucide-react";
import { ApiError, uploadDocument } from "@/lib/api";
import type { DocumentUploadResponse } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/toast";

const ACCEPT = ".pdf,.md,.txt";

export function UploadButton({
  onUploaded,
}: {
  onUploaded: (doc: DocumentUploadResponse) => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const { toast } = useToast();

  async function handleChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = ""; // 清空以允许重复选择同一文件
    if (!file) return;

    setBusy(true);
    try {
      const doc = await uploadDocument(file);
      onUploaded(doc);
      toast(`已上传 ${doc.filename}`, "success");
    } catch (err) {
      toast(err instanceof ApiError ? err.message : "上传失败", "error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col items-end gap-1.5">
      <input
        ref={inputRef}
        type="file"
        accept={ACCEPT}
        className="hidden"
        onChange={handleChange}
      />
      <Button onClick={() => inputRef.current?.click()} loading={busy}>
        {!busy && <Upload className="h-4 w-4" aria-hidden />}
        {busy ? "上传中…" : "上传文档"}
      </Button>
      <span className="text-xs text-mute">支持 .pdf / .md / .txt</span>
    </div>
  );
}
