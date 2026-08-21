"use client";

import Image from "next/image";
import { useCallback, useId, useRef, useState } from "react";

import { ApiError, uploadImage } from "@/lib/api";
import { ROUTE_BADGE_CLASS, ROUTE_LABEL, isTextRoute } from "@/lib/route-label";
import type { OcrRecord } from "@/lib/types";

export default function UploadCard() {
  const inputId = useId();
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragActive, setDragActive] = useState(false);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<OcrRecord | null>(null);

  const handleFile = useCallback(async (file: File) => {
    setError(null);
    setResult(null);
    setPreviewUrl(URL.createObjectURL(file));
    setLoading(true);
    try {
      const record = await uploadImage(file);
      setResult(record);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "업로드 중 오류가 발생했습니다.");
    } finally {
      setLoading(false);
    }
  }, []);

  const onInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) handleFile(file);
  };

  const onDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setDragActive(false);
    const file = e.dataTransfer.files?.[0];
    if (file) handleFile(file);
  };

  return (
    <section className="card" aria-labelledby="upload-heading">
      <h2 id="upload-heading" className="text-xl font-bold mb-1">
        이미지 업로드
      </h2>
      <p className="text-[var(--muted)] mb-4">
        영수증·명함·문서 이미지를 올리면 텍스트를 추출합니다. 사물 사진은 자동으로 사진 경로로 분류됩니다.
      </p>

      <div
        className={`dropzone${dragActive ? " dropzone-active" : ""}`}
        onDragOver={(e) => {
          e.preventDefault();
          setDragActive(true);
        }}
        onDragLeave={() => setDragActive(false)}
        onDrop={onDrop}
      >
        <label htmlFor={inputId} className="block cursor-pointer">
          <p className="font-medium mb-2">이미지를 이곳에 끌어다 놓거나 클릭해서 선택하세요</p>
          <p className="text-sm text-[var(--muted)]">JPEG · PNG · WEBP · BMP · TIFF 지원</p>
        </label>
        <input
          ref={inputRef}
          id={inputId}
          type="file"
          accept="image/jpeg,image/png,image/webp,image/bmp,image/tiff"
          className="sr-only"
          onChange={onInputChange}
        />
        <div className="mt-4">
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => inputRef.current?.click()}
            disabled={loading}
          >
            {loading ? "처리 중…" : "파일 선택"}
          </button>
        </div>
      </div>

      {previewUrl && (
        <div className="mt-5">
          <p className="text-sm font-medium mb-2">미리보기</p>
          <Image
            src={previewUrl}
            alt="업로드한 이미지 미리보기"
            width={320}
            height={200}
            unoptimized
            className="rounded-[var(--radius-md)] border border-[var(--border)] object-cover max-w-full h-auto"
          />
        </div>
      )}

      {loading && (
        <p role="status" aria-live="polite" className="mt-4 text-[var(--info)]">
          이미지를 분석하고 있습니다…
        </p>
      )}

      {error && (
        <p role="alert" aria-live="assertive" className="mt-4 badge badge-danger">
          {error}
        </p>
      )}

      {result && (
        <div className="mt-5 border-t border-[var(--border)] pt-4" aria-live="polite">
          <span className={ROUTE_BADGE_CLASS[result.route]}>{ROUTE_LABEL[result.route]}</span>
          {isTextRoute(result.route) ? (
            <pre className="mt-3 whitespace-pre-wrap break-words text-sm bg-[var(--background)] border border-[var(--border)] rounded-[var(--radius-md)] p-3">
              {result.extractedText || "추출된 텍스트가 없습니다."}
            </pre>
          ) : (
            <p className="mt-3 text-sm text-[var(--muted)]">
              사진으로 인식했습니다 — 설명 기능은 준비 중입니다.
              {result.description ? ` (${result.description})` : ""}
            </p>
          )}
        </div>
      )}
    </section>
  );
}
