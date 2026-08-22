import type { OcrRoute } from "./types";

export const ROUTE_LABEL: Record<OcrRoute, string> = {
  document: "문서로 인식",
  photo: "사진으로 인식",
  ambiguous_ocr: "문서로 판단(애매)",
  ambiguous_photo: "사진으로 판단(애매)",
  pdf_document: "PDF 문서",
  video_frames: "동영상 프레임",
  pptx_slides: "PPTX 문서",
  hwp_document: "HWP 문서",
  docx_document: "DOCX 문서",
};

export const ROUTE_BADGE_CLASS: Record<OcrRoute, string> = {
  document: "badge badge-success",
  ambiguous_ocr: "badge badge-info",
  photo: "badge badge-warn",
  ambiguous_photo: "badge badge-warn",
  pdf_document: "badge badge-success",
  video_frames: "badge badge-info",
  pptx_slides: "badge badge-success",
  hwp_document: "badge badge-success",
  docx_document: "badge badge-success",
};

export function isTextRoute(route: OcrRoute): boolean {
  return (
    route === "document" ||
    route === "ambiguous_ocr" ||
    route === "pdf_document" ||
    route === "video_frames" ||
    route === "pptx_slides" ||
    route === "hwp_document" ||
    route === "docx_document"
  );
}
