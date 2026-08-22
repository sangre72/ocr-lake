import type { OcrRecord, RecordListResponse } from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function parseJsonOrThrow(res: Response) {
  if (!res.ok) {
    let message = `요청이 실패했습니다 (${res.status})`;
    try {
      const body = await res.json();
      message = body?.detail ?? message;
    } catch {
      // 응답 본문이 JSON 이 아닐 수 있음 — 기본 메시지 사용
    }
    throw new ApiError(res.status, message);
  }
  return res.json();
}

export async function uploadImage(file: File): Promise<OcrRecord> {
  const formData = new FormData();
  formData.append("file", file);

  const res = await fetch(`${API_BASE}/api/upload`, {
    method: "POST",
    body: formData,
  });
  return parseJsonOrThrow(res);
}

export async function fetchRecords(page = 1, size = 20): Promise<RecordListResponse> {
  const res = await fetch(`${API_BASE}/api/records?page=${page}&size=${size}`, {
    cache: "no-store",
  });
  return parseJsonOrThrow(res);
}

export async function fetchRecord(id: number): Promise<OcrRecord> {
  const res = await fetch(`${API_BASE}/api/records/${id}`, {
    cache: "no-store",
  });
  return parseJsonOrThrow(res);
}

export async function structureRecord(
  id: number,
  docType: "auto" | "receipt" | "card" = "auto"
): Promise<OcrRecord> {
  const res = await fetch(`${API_BASE}/api/records/${id}/structure?doc_type=${docType}`, {
    method: "POST",
  });
  return parseJsonOrThrow(res);
}

export interface AdminJobEntry {
  seq: string;
  title: string;
  path: string;
  status?: string;
  assigned?: boolean;
  worker?: string | null;
}

export interface AdminJobQueueStatus {
  pendingU: AdminJobEntry[];
  pendingA: AdminJobEntry[];
  inProgress: AdminJobEntry[];
  doneRecent: AdminJobEntry[];
  errorRecent: AdminJobEntry[];
}

export async function fetchAdminJobQueue(): Promise<AdminJobQueueStatus> {
  const res = await fetch(`${API_BASE}/api/admin/jobs`);
  return parseJsonOrThrow(res);
}
