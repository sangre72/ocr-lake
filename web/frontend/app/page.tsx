import UploadCard from "@/components/UploadCard";

export default function HomePage() {
  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-extrabold mb-1">OCR Lake</h1>
        <p className="text-[var(--muted)]">이미지를 업로드해 텍스트를 추출하거나 처리 이력을 확인하세요.</p>
      </div>
      <UploadCard />
    </div>
  );
}
