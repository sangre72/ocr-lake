"use client";

import Link from "next/link";
import { useEffect, useId, useState } from "react";

import { ApiError, correctRecordText, fetchRecord, structureRecord } from "@/lib/api";
import { ROUTE_BADGE_CLASS, ROUTE_LABEL, isTextRoute } from "@/lib/route-label";
import type { OcrRecord } from "@/lib/types";

export default function RecordDetail({ id }: { id: number }) {
  const correctionFieldId = useId();
  const [record, setRecord] = useState<OcrRecord | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [structuring, setStructuring] = useState(false);
  const [structureError, setStructureError] = useState<string | null>(null);
  const [editingText, setEditingText] = useState("");
  const [isEditing, setIsEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  const handleStructure = async () => {
    setStructuring(true);
    setStructureError(null);
    try {
      const updated = await structureRecord(id);
      setRecord(updated);
    } catch (err) {
      setStructureError(
        err instanceof ApiError ? err.message : "구조화 처리 중 오류가 발생했습니다."
      );
    } finally {
      setStructuring(false);
    }
  };

  const startEditing = () => {
    setEditingText(record?.correctedText ?? record?.extractedText ?? "");
    setSaveError(null);
    setIsEditing(true);
  };

  const handleSaveCorrection = async () => {
    if (!editingText.trim()) {
      setSaveError("수정된 텍스트는 비워둘 수 없습니다.");
      return;
    }
    setSaving(true);
    setSaveError(null);
    try {
      const updated = await correctRecordText(id, editingText);
      setRecord(updated);
      setIsEditing(false);
    } catch (err) {
      setSaveError(err instanceof ApiError ? err.message : "수정 저장 중 오류가 발생했습니다.");
    } finally {
      setSaving(false);
    }
  };

  useEffect(() => {
    let cancelled = false;
    fetchRecord(id)
      .then((r) => {
        if (!cancelled) setRecord(r);
      })
      .catch(() => {
        if (!cancelled) setError("이력을 찾을 수 없습니다.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [id]);

  return (
    <section className="flex flex-col gap-4">
      <Link href="/records" className="text-sm underline decoration-dotted hover:decoration-solid w-fit">
        ← 목록으로
      </Link>

      {loading && (
        <p role="status" aria-live="polite" className="text-[var(--info)]">
          불러오는 중…
        </p>
      )}
      {error && (
        <p role="alert" className="badge badge-danger">
          {error}
        </p>
      )}

      {record && (
        <div className="card">
          <div className="flex items-center gap-3 mb-3">
            <span className={ROUTE_BADGE_CLASS[record.route]}>{ROUTE_LABEL[record.route]}</span>
            <span className="text-sm text-[var(--muted)]">{record.createdAt}</span>
          </div>
          {isTextRoute(record.route) ? (
            <>
              {record.isCorrected && (
                <p className="badge badge-info mb-2">사람이 검수·수정한 결과입니다({record.correctedAt})</p>
              )}

              <p className="text-sm font-medium mb-1">
                {record.isCorrected ? "수정된 텍스트" : "추출된 텍스트"}
              </p>
              <pre className="whitespace-pre-wrap break-words text-sm bg-[var(--background)] border border-[var(--border)] rounded-[var(--radius-md)] p-3">
                {record.correctedText || record.extractedText || "추출된 텍스트가 없습니다."}
              </pre>

              {record.isCorrected && record.extractedText && (
                <details className="mt-2">
                  <summary className="text-sm text-[var(--muted)] cursor-pointer">
                    원본 OCR 결과 보기(대조)
                  </summary>
                  <pre className="mt-2 whitespace-pre-wrap break-words text-sm bg-[var(--background)] border border-[var(--border)] rounded-[var(--radius-md)] p-3">
                    {record.extractedText}
                  </pre>
                </details>
              )}

              {record.extractedText && !isEditing && (
                <div className="mt-3">
                  <button type="button" className="btn btn-secondary" onClick={startEditing}>
                    텍스트 수정하기
                  </button>
                </div>
              )}

              {isEditing && (
                <div className="mt-3">
                  <label htmlFor={correctionFieldId} className="block text-sm font-medium mb-1">
                    수정된 텍스트
                  </label>
                  <textarea
                    id={correctionFieldId}
                    className="w-full min-w-0 rounded-[var(--radius-md)] border border-[var(--border)] bg-[var(--background)] p-3 text-sm"
                    rows={8}
                    value={editingText}
                    onChange={(e) => setEditingText(e.target.value)}
                    aria-invalid={saveError ? "true" : undefined}
                    aria-describedby={saveError ? `${correctionFieldId}-error` : undefined}
                  />
                  <div className="mt-2 flex gap-2">
                    <button
                      type="button"
                      className="btn btn-primary"
                      onClick={handleSaveCorrection}
                      disabled={saving}
                    >
                      {saving ? "저장 중…" : "저장"}
                    </button>
                    <button
                      type="button"
                      className="btn btn-secondary"
                      onClick={() => setIsEditing(false)}
                      disabled={saving}
                    >
                      취소
                    </button>
                  </div>
                  {saveError && (
                    <p
                      id={`${correctionFieldId}-error`}
                      role="alert"
                      aria-live="assertive"
                      className="mt-2 badge badge-danger"
                    >
                      {saveError}
                    </p>
                  )}
                </div>
              )}

              {record.extractedText && (
                <div className="mt-4">
                  <button
                    type="button"
                    className="btn btn-primary"
                    onClick={handleStructure}
                    disabled={structuring}
                  >
                    {structuring ? "구조화 중…" : "AI로 구조화하기"}
                  </button>

                  {structuring && (
                    <p role="status" aria-live="polite" className="mt-2 text-sm text-[var(--info)]">
                      로컬 모델로 텍스트를 구조화하고 있습니다…
                    </p>
                  )}

                  {structureError && (
                    <p role="alert" aria-live="assertive" className="mt-2 badge badge-danger">
                      {structureError}
                    </p>
                  )}

                  {record.structuredJson && (
                    <pre
                      className="mt-3 whitespace-pre-wrap break-words text-sm bg-[var(--background)] border border-[var(--border)] rounded-[var(--radius-md)] p-3"
                      aria-live="polite"
                    >
                      {JSON.stringify(record.structuredJson, null, 2)}
                    </pre>
                  )}
                </div>
              )}
            </>
          ) : (
            <p className="text-sm text-[var(--muted)]">
              사진으로 인식했습니다 — 설명 기능은 준비 중입니다.
              {record.description ? ` (${record.description})` : ""}
            </p>
          )}
        </div>
      )}
    </section>
  );
}
