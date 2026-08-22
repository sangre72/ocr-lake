export type OcrRoute =
  | "document"
  | "photo"
  | "ambiguous_ocr"
  | "ambiguous_photo"
  | "pdf_document"
  | "video_frames"
  | "pptx_slides"
  | "hwp_document"
  | "docx_document";

export interface OcrRecord {
  id: number;
  createdAt: string;
  source: "telegram" | "web" | "discord" | "slack";
  imagePath: string | null;
  route: OcrRoute;
  extractedText: string | null;
  description: string | null;
  structuredJson: Record<string, unknown> | null;
  chatId: number | null;
  correctedText: string | null;
  isCorrected: boolean;
  correctedAt: string | null;
  originalConfidence: number | null;
}

export interface RecordListResponse {
  records: OcrRecord[];
  total: number;
  page: number;
  size: number;
}
