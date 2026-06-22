import type { LucideIcon } from "lucide-react";

export function EmptyState({
  icon: Icon,
  title,
  hint,
  action,
}: {
  icon?: LucideIcon;
  title: string;
  hint?: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 rounded-sm bg-canvas-soft px-6 py-14 text-center">
      {Icon && <Icon className="h-8 w-8 text-mute" aria-hidden />}
      <p className="text-base text-body">{title}</p>
      {hint && <p className="max-w-sm text-sm text-mute">{hint}</p>}
      {action && <div className="mt-2">{action}</div>}
    </div>
  );
}
