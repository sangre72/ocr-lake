"""텔레그램 저수준 I/O — 표준 라이브러리(urllib)만 사용.

python-telegram-bot 같은 무거운 의존성 없이 Bot API를 직접 호출한다.
long-polling(getUpdates) + sendMessage 두 가지만 쓴다.
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from typing import Any


class TelegramIO:
    def __init__(self, token: str, timeout: int = 30) -> None:
        self.base = f"https://api.telegram.org/bot{token}"
        # 파일 다운로드용 베이스 (getFile 의 file_path 를 붙여 사용)
        self.file_base = f"https://api.telegram.org/file/bot{token}"
        self.timeout = timeout

    def _call(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.base}/{method}"
        data = urllib.parse.urlencode(
            {k: v for k, v in params.items() if v is not None}
        ).encode()
        req = urllib.request.Request(url, data=data)
        with urllib.request.urlopen(req, timeout=self.timeout + 5) as resp:
            payload = json.loads(resp.read().decode())
        if not payload.get("ok"):
            raise RuntimeError(f"Telegram {method} 실패: {payload}")
        return payload["result"]

    def get_me(self) -> dict[str, Any]:
        return self._call("getMe", {})

    def get_updates(
        self,
        offset: int | None = None,
        allowed_updates: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """long-polling. offset 이후의 새 업데이트만 반환.

        allowed_updates 를 지정하면 그 종류만(예: ["callback_query"]) 수신한다.
        미지정 시 기본은 message (오케 중계기 호환).
        """
        return self._call(
            "getUpdates",
            {
                "offset": offset,
                "timeout": self.timeout,
                "allowed_updates": json.dumps(allowed_updates or ["message"]),
            },
        )

    def send_message(
        self, chat_id: int, text: str, parse_mode: str | None = None
    ) -> dict[str, Any]:
        # 텔레그램 메시지 길이 제한(4096) 대응 — 넘으면 잘라 여러 번 전송
        limit = 4000
        result: dict[str, Any] = {}
        for i in range(0, max(len(text), 1), limit):
            chunk = text[i : i + limit] or " "
            result = self._call(
                "sendMessage",
                {"chat_id": chat_id, "text": chunk, "parse_mode": parse_mode},
            )
        return result

    def send_message_kb(
        self,
        chat_id: int,
        text: str,
        inline_keyboard: list[list[dict[str, Any]]] | None = None,
        parse_mode: str | None = None,
    ) -> dict[str, Any]:
        """inline keyboard 를 붙인 sendMessage.

        inline_keyboard 예: [[{"text": "후보1", "callback_data": "..."}], ...]
        """
        params: dict[str, Any] = {
            "chat_id": chat_id,
            "text": (text[:4000] or " "),
            "parse_mode": parse_mode,
        }
        if inline_keyboard:
            params["reply_markup"] = json.dumps({"inline_keyboard": inline_keyboard})
        return self._call("sendMessage", params)

    def send_photo(
        self,
        chat_id: int,
        photo: str,
        caption: str | None = None,
        inline_keyboard: list[list[dict[str, Any]]] | None = None,
    ) -> dict[str, Any]:
        """sendPhoto. photo 는 URL 또는 file_id (문자열). 캡션/인라인키보드 선택.

        로컬 파일 업로드는 send_photo_file 을 사용한다(멀티파트).
        """
        params: dict[str, Any] = {
            "chat_id": chat_id,
            "photo": photo,
            "caption": (caption or "")[:1024] or None,
        }
        if inline_keyboard:
            params["reply_markup"] = json.dumps({"inline_keyboard": inline_keyboard})
        return self._call("sendPhoto", params)

    def send_photo_file(
        self,
        chat_id: int,
        file_path,
        caption: str | None = None,
        inline_keyboard: list[list[dict[str, Any]]] | None = None,
    ) -> dict[str, Any]:
        """로컬 이미지 파일을 멀티파트로 업로드하는 sendPhoto."""
        from pathlib import Path as _P

        p = _P(file_path)
        fields: dict[str, str] = {"chat_id": str(chat_id)}
        if caption:
            fields["caption"] = caption[:1024]
        if inline_keyboard:
            fields["reply_markup"] = json.dumps({"inline_keyboard": inline_keyboard})
        body, content_type = self._encode_multipart(
            fields, [("photo", p.name, p.read_bytes())]
        )
        req = urllib.request.Request(
            f"{self.base}/sendPhoto", data=body,
            headers={"Content-Type": content_type},
        )
        with urllib.request.urlopen(req, timeout=self.timeout + 30) as resp:
            payload = json.loads(resp.read().decode())
        if not payload.get("ok"):
            raise RuntimeError(f"Telegram sendPhoto 실패: {payload}")
        return payload["result"]

    def answer_callback_query(
        self, callback_query_id: str, text: str | None = None
    ) -> dict[str, Any]:
        """콜백 버튼 클릭에 응답(로딩 스피너 종료 + 토스트)."""
        return self._call(
            "answerCallbackQuery",
            {"callback_query_id": callback_query_id, "text": text},
        )

    def edit_message_reply_markup(
        self,
        chat_id: int,
        message_id: int,
        inline_keyboard: list[list[dict[str, Any]]] | None = None,
    ) -> dict[str, Any]:
        """선택 후 버튼을 갱신/제거(중복 클릭 방지·확정 표시)."""
        params: dict[str, Any] = {"chat_id": chat_id, "message_id": message_id}
        params["reply_markup"] = json.dumps(
            {"inline_keyboard": inline_keyboard or []}
        )
        return self._call("editMessageReplyMarkup", params)

    @staticmethod
    def _encode_multipart(
        fields: dict[str, str], files: list[tuple[str, str, bytes]]
    ) -> tuple[bytes, str]:
        """multipart/form-data 인코딩 (표준 라이브러리만)."""
        boundary = "----CineBotBoundary7MA4YWxkTrZu0gW"
        lines: list[bytes] = []
        for name, value in fields.items():
            lines.append(f"--{boundary}".encode())
            lines.append(
                f'Content-Disposition: form-data; name="{name}"'.encode()
            )
            lines.append(b"")
            lines.append(str(value).encode())
        for name, filename, data in files:
            lines.append(f"--{boundary}".encode())
            lines.append(
                f'Content-Disposition: form-data; name="{name}"; '
                f'filename="{filename}"'.encode()
            )
            lines.append(b"Content-Type: application/octet-stream")
            lines.append(b"")
            lines.append(data)
        lines.append(f"--{boundary}--".encode())
        lines.append(b"")
        body = b"\r\n".join(lines)
        return body, f"multipart/form-data; boundary={boundary}"

    def get_file(self, file_id: str) -> dict[str, Any]:
        """getFile — file_id 로 서버측 file_path 를 조회한다."""
        return self._call("getFile", {"file_id": file_id})

    def download_file(self, file_path: str, dest) -> None:
        """getFile 로 얻은 file_path 를 실제 바이트로 내려받아 dest(Path)에 저장한다."""
        url = f"{self.file_base}/{file_path}"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=self.timeout + 30) as resp:
            data = resp.read()
        dest.write_bytes(data)
