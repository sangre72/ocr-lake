"""OCR 웹 업로드/이력 조회 API 라우트.

보안(security-guideline.md 최우선): 업로드 파일은 확장자·MIME·PIL 오픈검증(ALLOWED_FORMATS)을
거치고, 저장 파일명은 서버에서 uuid4 로 랜덤 생성한다(원본 파일명 신뢰 금지).
API 응답 키는 naming-standard.md 에 따라 camelCase(record_to_dict 가 변환 담당).
"""

import logging
import uuid
from io import BytesIO
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from PIL import Image

from core.ocr.engine import ALLOWED_FORMATS, UnsupportedImageError
from core.ocr.structurer import StructurerNotConfiguredError, structure_text
from core.pdf import UnsupportedPdfError, process_pdf
from core.pipeline import process_image
from core.storage import get_record, list_records, record_to_dict, save_record, update_structured_json
from core.video import UnsupportedVideoError, process_video

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api")

UPLOAD_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "uploads"
MAX_UPLOAD_BYTES = 20 * 1024 * 1024  # 20MB — 이미지/PDF
MAX_VIDEO_BYTES = 100 * 1024 * 1024  # 100MB — 동영상은 더 큰 편이라 별도 상한

_EXT_BY_FORMAT = {
    "JPEG": ".jpg",
    "PNG": ".png",
    "WEBP": ".webp",
    "BMP": ".bmp",
    "TIFF": ".tiff",
}

# 실행파일/스크립트는 여전히 차단(security-guideline.md) — 이미지 + pdf/mp4 만 화이트리스트 확장
_PDF_CONTENT_TYPES = {"application/pdf"}
_VIDEO_CONTENT_TYPES = {"video/mp4", "video/quicktime", "video/webm", "video/x-msvideo"}


def _store_upload(raw_bytes: bytes, ext: str) -> Path:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    stored_path = UPLOAD_DIR / f"{uuid.uuid4().hex}{ext}"
    stored_path.write_bytes(raw_bytes)
    return stored_path


@router.post("/upload")
async def upload_image(file: UploadFile = File(...)) -> dict:
    content_type = (file.content_type or "").lower()
    raw_bytes = await file.read()

    if content_type in _PDF_CONTENT_TYPES:
        return await _handle_pdf_upload(raw_bytes)
    if content_type in _VIDEO_CONTENT_TYPES:
        return await _handle_video_upload(raw_bytes)
    return await _handle_image_upload(raw_bytes)


async def _handle_image_upload(image_bytes: bytes) -> dict:
    if len(image_bytes) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="이미지가 너무 큽니다(최대 20MB).")

    try:
        result = await process_image(image_bytes)
    except UnsupportedImageError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("웹 업로드 이미지 처리 중 오류")
        raise HTTPException(status_code=500, detail="이미지 처리 중 오류가 발생했습니다.") from exc

    # 실제 이미지 포맷을 다시 확인해 저장 확장자 결정(요청 파일명은 신뢰하지 않음)
    fmt = Image.open(BytesIO(image_bytes)).format
    if fmt not in ALLOWED_FORMATS:
        raise HTTPException(status_code=400, detail=f"지원하지 않는 이미지 포맷입니다: {fmt}")

    stored_path = _store_upload(image_bytes, _EXT_BY_FORMAT.get(fmt, ".bin"))
    record_id = save_record(
        source="web",
        route=result.route,
        image_path=str(stored_path.relative_to(UPLOAD_DIR.parent.parent)),
        extracted_text=result.text,
        description=result.description,
    )
    return record_to_dict(get_record(record_id))


async def _handle_pdf_upload(pdf_bytes: bytes) -> dict:
    if len(pdf_bytes) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="PDF가 너무 큽니다(최대 20MB).")

    try:
        result = await process_pdf(pdf_bytes)
    except UnsupportedPdfError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("웹 업로드 PDF 처리 중 오류")
        raise HTTPException(status_code=500, detail="PDF 처리 중 오류가 발생했습니다.") from exc

    stored_path = _store_upload(pdf_bytes, ".pdf")
    record_id = save_record(
        source="web",
        route="pdf_document",
        image_path=str(stored_path.relative_to(UPLOAD_DIR.parent.parent)),
        extracted_text=result.combined_text,
        description=f"PDF {result.page_count}페이지 처리",
        structured_json={
            "pages": [
                {"pageNumber": p.page_number, "route": p.pipeline_result.route}
                for p in result.pages
            ]
        },
    )
    return record_to_dict(get_record(record_id))


async def _handle_video_upload(video_bytes: bytes) -> dict:
    if len(video_bytes) > MAX_VIDEO_BYTES:
        raise HTTPException(status_code=413, detail="동영상이 너무 큽니다(최대 100MB).")

    try:
        result = await process_video(video_bytes)
    except UnsupportedVideoError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("웹 업로드 동영상 처리 중 오류")
        raise HTTPException(status_code=500, detail="동영상 처리 중 오류가 발생했습니다.") from exc

    stored_path = _store_upload(video_bytes, ".mp4")
    record_id = save_record(
        source="web",
        route="video_frames",
        image_path=str(stored_path.relative_to(UPLOAD_DIR.parent.parent)),
        extracted_text=result.combined_text or None,
        description=f"동영상 {result.frame_count_sampled}프레임 샘플링, "
        f"{len(result.document_frames)}개 프레임에서 텍스트 발견",
        structured_json={
            "frameCountSampled": result.frame_count_sampled,
            "documentFrames": [
                {"timestampSec": f.timestamp_sec} for f in result.document_frames
            ],
        },
    )
    return record_to_dict(get_record(record_id))


@router.get("/records")
async def get_records(page: int = 1, size: int = 20) -> dict:
    records, total = list_records(page=page, size=size)
    return {
        "records": [record_to_dict(r) for r in records],
        "total": total,
        "page": page,
        "size": size,
    }


@router.get("/records/{record_id}")
async def get_record_detail(record_id: int) -> dict:
    record = get_record(record_id)
    if record is None:
        raise HTTPException(status_code=404, detail="레코드를 찾을 수 없습니다.")
    return record_to_dict(record)


@router.post("/records/{record_id}/structure")
async def structure_record(record_id: int, doc_type: str = "auto") -> dict:
    """저장된 이력의 추출 텍스트를 로컬 LLM(MLX)으로 구조화하고 structured_json 컬럼에 저장한다.

    온디맨드 방식(업로드 시 자동 구조화 대신 필요할 때 호출) — MLX 모델 추론 시간을 고려한 선택.
    """
    record = get_record(record_id)
    if record is None:
        raise HTTPException(status_code=404, detail="레코드를 찾을 수 없습니다.")
    if not record.extracted_text:
        raise HTTPException(status_code=400, detail="구조화할 텍스트가 없는 레코드입니다.")

    try:
        structured = await structure_text(record.extracted_text, doc_type=doc_type)
    except StructurerNotConfiguredError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("웹 구조화 처리 중 오류")
        raise HTTPException(status_code=500, detail="구조화 처리 중 오류가 발생했습니다.") from exc

    update_structured_json(record_id, structured)
    return record_to_dict(get_record(record_id))
