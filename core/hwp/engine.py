"""아래아한글(.hwp, HWP 5.0 바이너리 포맷) 텍스트 추출.

HWP 파일 내부의 텍스트는 이미 구조화된 문자열(OLE2 컨테이너에 압축 저장)이라, PDF/이미지처럼
OCR이 필요 없다 — 순수 텍스트 추출 라이브러리(hwp-hwpx-parser)로 직접 읽는다.
HWPX(신버전, XML 기반)는 이번 스코프 아님(구버전 .hwp 5.x만 지원).
"""

import logging
import tempfile
from dataclasses import dataclass
from pathlib import Path

from hwp_hwpx_parser import extract_hwp5

logger = logging.getLogger(__name__)


class UnsupportedHwpError(ValueError):
    """HWP 파일을 열 수 없거나 텍스트를 추출할 수 없는 경우"""


@dataclass
class HwpOcrResult:
    combined_text: str


def process_hwp(hwp_bytes: bytes) -> HwpOcrResult:
    """HWP(5.x) 파일에서 텍스트를 추출한다.

    Args:
        hwp_bytes: HWP 원본 바이트

    Returns:
        HwpOcrResult: 추출된 전체 텍스트(combined_text)

    Raises:
        UnsupportedHwpError: HWP 파일을 열 수 없거나 파싱에 실패한 경우
    """
    # extract_hwp5 는 파일 경로 기반 API 라 임시파일로 기록 후 처리한다(core/video 의 cv2 패턴과 동일 이유).
    with tempfile.NamedTemporaryFile(suffix=".hwp", delete=False) as tmp:
        tmp.write(hwp_bytes)
        tmp_path = Path(tmp.name)

    try:
        text, error = extract_hwp5(str(tmp_path))
    except Exception as exc:
        raise UnsupportedHwpError("HWP 파일을 열 수 없습니다.") from exc
    finally:
        tmp_path.unlink(missing_ok=True)

    if error:
        raise UnsupportedHwpError(f"HWP 파싱 중 오류가 발생했습니다: {error}")
    if not text or not text.strip():
        raise UnsupportedHwpError("HWP 파일에서 텍스트를 찾을 수 없습니다.")

    return HwpOcrResult(combined_text=text.strip())
