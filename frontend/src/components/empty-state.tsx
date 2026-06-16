export function EmptyState({ title, hint }: { title: string; hint?: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 rounded-sm bg-canvas-soft px-6 py-12 text-center">
      <p className="text-base text-body">{title}</p>
      {hint && <p className="text-sm text-mute">{hint}</p>}
    </div>
  );
}
