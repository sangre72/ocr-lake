import RecordDetail from "@/components/RecordDetail";

export default async function RecordDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <RecordDetail id={Number(id)} />;
}
