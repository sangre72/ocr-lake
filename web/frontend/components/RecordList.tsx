"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { fetchRecords } from "@/lib/api";
import { ROUTE_BADGE_CLASS, ROUTE_LABEL } from "@/lib/route-label";
import type { OcrRecord } from "@/lib/types";

const PAGE_SIZE = 10;

export default function RecordList() {
  const [page, setPage] = useState(1);
  const [records, setRecords] = useState<OcrRecord[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetchRecords(page, PAGE_SIZE)
      .then((res) => {
        if (cancelled) return;
        setRecords(res.records);
        setTotal(res.total);
      })
      .catch(() => {
        if (!cancelled) setError("처리 이력을 불러오지 못했습니다.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [page]);

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <section aria-labelledby="records-heading" className="flex flex-col gap-4">
      <h1 id="records-heading" className="text-2xl font-extrabold">
        처리 이력
      </h1>

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

      {!loading && !error && records.length === 0 && (
        <p className="text-[var(--muted)]">아직 처리한 이미지가 없습니다.</p>
      )}

      {records.length > 0 && (
        <div className="card overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <caption className="sr-only">OCR 처리 이력 목록</caption>
            <thead>
              <tr className="border-b border-[var(--border)] text-sm text-[var(--muted)]">
                <th scope="col" className="py-2 pr-3">
                  일시
                </th>
                <th scope="col" className="py-2 pr-3">
                  경로
                </th>
                <th scope="col" className="py-2 pr-3">
                  출처
                </th>
                <th scope="col" className="py-2">
                  내용 미리보기
                </th>
              </tr>
            </thead>
            <tbody>
              {records.map((record) => (
                <tr key={record.id} className="border-b border-[var(--border)] last:border-0">
                  <td className="py-2 pr-3 align-top whitespace-nowrap text-sm">
                    <Link
                      href={`/records/${record.id}`}
                      className="underline decoration-dotted hover:decoration-solid"
                    >
                      {record.createdAt}
                    </Link>
                  </td>
                  <td className="py-2 pr-3 align-top">
                    <span className={ROUTE_BADGE_CLASS[record.route]}>{ROUTE_LABEL[record.route]}</span>
                  </td>
                  <td className="py-2 pr-3 align-top text-sm">
                    {record.source === "telegram" ? "텔레그램" : "웹"}
                  </td>
                  <td className="py-2 align-top text-sm max-w-xs truncate">
                    {record.extractedText || record.description || "-"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {totalPages > 1 && (
        <nav aria-label="이력 페이지 이동" className="flex items-center gap-3">
          <button
            type="button"
            className="btn btn-primary"
            disabled={page <= 1}
            onClick={() => setPage((p) => Math.max(1, p - 1))}
          >
            이전
          </button>
          <span className="text-sm text-[var(--muted)]">
            {page} / {totalPages} 페이지
          </span>
          <button
            type="button"
            className="btn btn-primary"
            disabled={page >= totalPages}
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
          >
            다음
          </button>
        </nav>
      )}
    </section>
  );
}
