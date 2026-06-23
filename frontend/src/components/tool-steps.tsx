import type { IntermediateStep } from "@/lib/types";

function statusDot(status: string): string {
  if (status === "ok") return "bg-success";
  if (status === "error") return "bg-destructive";
  return "bg-info";
}

// Agent 的 ReAct 多步推理轨迹，默认折叠（点开看每一步调了什么工具、入参、成败）。
export function ToolSteps({ steps }: { steps: IntermediateStep[] }) {
  if (steps.length === 0) return null;

  return (
    <details className="mt-3 rounded-sm border border-border bg-muted">
      <summary className="cursor-pointer select-none px-4 py-2 font-mono text-caption-mono-sm uppercase text-muted-foreground">
        推理轨迹 · {steps.length} 步
      </summary>
      <ol className="border-t border-border">
        {steps.map((s) => (
          <li
            key={s.step}
            className="flex items-start gap-3 border-b border-border px-4 py-2.5 last:border-b-0"
          >
            <span className="mt-0.5 font-mono text-caption-mono-sm text-muted-foreground">#{s.step}</span>
            <span className={`mt-2 h-1.5 w-1.5 shrink-0 rounded-full ${statusDot(s.status)}`} />
            <div className="min-w-0">
              <span className="font-mono text-sm text-foreground">{s.action}</span>
              <p className="mt-0.5 break-words font-mono text-caption-mono-sm text-muted-foreground">
                {s.detail}
              </p>
            </div>
          </li>
        ))}
      </ol>
    </details>
  );
}
