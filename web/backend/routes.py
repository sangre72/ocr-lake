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

from telegram_bot.ocr.engine import ALLOWED_FORMATS, UnsupportedImageError
from telegram_bot.pipeline import process_image
from telegram_bot.storage import get_record, list_records, record_to_dict, save_record

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api")

UPLOAD_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "uploads"
MAX_UPLOAD_BYTES = 20 * 1024 * 1024  # 20MB — telegram_bot.config 의 기본 max_image_size_mb 와 동일

_EXT_BY_FORMAT = {
    "JPEG": ".jpg",
    "PNG": ".png",
    "WEBP": ".webp",
    "BMP": ".bmp",
    "TIFF": ".tiff",
}


@router.post("/upload")
async def upload_image(file: UploadFile = File(...)) -> dict:
    image_bytes = await file.read()

    if len(image_bytes) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="이미지가 너무 큽니다(최대 20MB).")

    try:
        result = await process_image(image_bytes)
    except UnsupportedImageError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception:
        logger.exception("웹 업로드 이미지 처리 중 오류")
        raise HTTPException(status_code=500, detail="이미지 처리 중 오류가 발생했습니다.") from exc

    # 실제 이미지 포맷을 다시 확인해 저장 확장자 결정(요청 파일명은 신뢰하지 않음)
    fmt = Image.open(BytesIO(image_bytes)).format
    if fmt not in ALLOWED_FORMATS:
        raise HTTPException(status_code=400, detail=f"지원하지 않는 이미지 포맷입니다: {fmt}")

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    stored_name = f"{uuid.uuid4().hex}{_EXT_BY_FORMAT.get(fmt, '.bin')}"
    stored_path = UPLOAD_DIR / stored_name
    stored_path.write_bytes(image_bytes)

    record_id = save_record(
        source="web",
        route=result.route,
        image_path=str(stored_path.relative_to(UPLOAD_DIR.parent.parent)),
        extracted_text=result.text,
        description=result.description,
    )

    record = get_record(record_id)
    return record_to_dict(record)


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
