"""동영상 프레임 샘플링 + 기존 파이프라인 재사용.

N초 간격으로 프레임을 추출해 telegram_bot.pipeline.process_image 에 그대로 태운다
(code-structure.md §7 — 분류/OCR 로직 재발명 금지). "document"로 분류된 프레임만
텍스트 추출 결과를 남기고, 사물/배경(photo) 프레임은 스킵한다.
"""

import io
import logging
import tempfile
from dataclasses import dataclass
from pathlib import Path

import cv2

from core.pipeline import PipelineResult, process_image

logger = logging.getLogger(__name__)

# 긴 영상 전체 프레임화 방지(자원낭비 방지 — 기본 샘플링 간격 + 최대 프레임 수 상한)
DEFAULT_SAMPLE_INTERVAL_SEC = 2.5
MAX_FRAMES = 30


class UnsupportedVideoError(ValueError):
    """동영상 파일을 열 수 없거나 프레임이 없는 경우"""


@dataclass
class VideoFrameResult:
    timestamp_sec: float
    pipeline_result: PipelineResult


@dataclass
class VideoOcrResult:
    frame_count_sampled: int
    document_frames: list[VideoFrameResult]
    combined_text: str


def _extract_frame_bytes(capture: cv2.VideoCapture, frame_index: int) -> bytes | None:
    capture.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
    ok, frame = capture.read()
    if not ok or frame is None:
        return None
    ok, buf = cv2.imencode(".png", frame)
    if not ok:
        return None
    return buf.tobytes()


async def process_video(
    video_bytes: bytes,
    lang: str = "kor+eng",
    sample_interval_sec: float = DEFAULT_SAMPLE_INTERVAL_SEC,
    max_frames: int = MAX_FRAMES,
) -> VideoOcrResult:
    """동영상에서 N초 간격으로 프레임을 샘플링해 문서로 판단된 프레임만 OCR 결과로 남긴다.

    Args:
        video_bytes: 동영상 원본 바이트
        lang: tesseract 언어 코드
        sample_interval_sec: 프레임 샘플링 간격(초)
        max_frames: 최대 샘플링 프레임 수 상한

    Returns:
        VideoOcrResult: document 로 분류된 프레임 목록 + 이어붙인 텍스트

    Raises:
        UnsupportedVideoError: 동영상을 열 수 없거나 프레임이 없는 경우
    """
    # cv2.VideoCapture 는 파일 경로 기반이 안정적이라 임시파일로 기록 후 처리한다.
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
        tmp.write(video_bytes)
        tmp_path = Path(tmp.name)

    try:
        capture = cv2.VideoCapture(str(tmp_path))
        if not capture.isOpened():
            raise UnsupportedVideoError("동영상 파일을 열 수 없습니다.")

        fps = capture.get(cv2.CAP_PROP_FPS) or 0
        total_frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        if fps <= 0 or total_frames <= 0:
            capture.release()
            raise UnsupportedVideoError("동영상 메타데이터를 읽을 수 없습니다.")

        duration_sec = total_frames / fps
        step_frames = max(int(fps * sample_interval_sec), 1)

        sample_indices = list(range(0, total_frames, step_frames))[:max_frames]
        if len(sample_indices) < len(range(0, total_frames, step_frames)):
            logger.warning(
                "동영상 길이(%.1fs)에 비해 프레임 상한(%d)을 넘어 앞부분만 샘플링합니다.",
                duration_sec, max_frames,
            )

        document_frames: list[VideoFrameResult] = []
        text_chunks: list[str] = []

        for frame_index in sample_indices:
            frame_bytes = _extract_frame_bytes(capture, frame_index)
            if frame_bytes is None:
                continue

            timestamp_sec = frame_index / fps
            try:
                result = await process_image(frame_bytes, lang=lang)
            except Exception:
                logger.exception("프레임(%.1fs) OCR 처리 중 오류 — 스킵", timestamp_sec)
                continue

            if result.route in ("document", "ambiguous_ocr") and result.text:
                document_frames.append(
                    VideoFrameResult(timestamp_sec=timestamp_sec, pipeline_result=result)
                )
                text_chunks.append(f"[{timestamp_sec:.1f}s]\n{result.text}")

        capture.release()

        combined_text = "\n\n".join(text_chunks)
        return VideoOcrResult(
            frame_count_sampled=len(sample_indices),
            document_frames=document_frames,
            combined_text=combined_text,
        )
    finally:
        tmp_path.unlink(missing_ok=True)
