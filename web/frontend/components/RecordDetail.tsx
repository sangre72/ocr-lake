"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { fetchRecord } from "@/lib/api";
import { ROUTE_BADGE_CLASS, ROUTE_LABEL, isTextRoute } from "@/lib/route-label";
import type { OcrRecord } from "@/lib/types";

export default function RecordDetail({ id }: { id: number }) {
  const [record, setRecord] = useState<OcrRecord | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

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
            <pre className="whitespace-pre-wrap break-words text-sm bg-[var(--background)] border border-[var(--border)] rounded-[var(--radius-md)] p-3">
              {record.extractedText || "추출된 텍스트가 없습니다."}
            </pre>
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
