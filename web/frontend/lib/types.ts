export type OcrRoute =
  | "document"
  | "photo"
  | "ambiguous_ocr"
  | "ambiguous_photo"
  | "pdf_document"
  | "video_frames";

export interface OcrRecord {
  id: number;
  createdAt: string;
  source: "telegram" | "web";
  imagePath: string | null;
  route: OcrRoute;
  extractedText: string | null;
  description: string | null;
  structuredJson: Record<string, unknown> | null;
  chatId: number | null;
}

export interface RecordListResponse {
  records: OcrRecord[];
  total: number;
  page: number;
  size: number;
}
