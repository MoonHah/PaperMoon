import { redirect } from "next/navigation";

// /documents/[id] 默认进「阅读」tab。
export default async function DocumentIndex({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  redirect(`/documents/${id}/read`);
}
