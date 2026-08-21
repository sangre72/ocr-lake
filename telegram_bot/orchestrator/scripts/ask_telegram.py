#!/usr/bin/env python3
"""오케 → 유저 텔레그램 버튼 질문 발송. 유저는 폰에서 버튼으로 답.
사용: python3 telegram_bot/orchestrator/scripts/ask_telegram.py "질문텍스트" "옵션1|cbdata1" ...
콜백은 봇(orchestrator)이 받아 u_*.txt 로 남김. callback_data 규약: ask|<key>|<value>

경로(u_136 이동): 이 파일 = <repo>/telegram_bot/orchestrator/scripts/ask_telegram.py
  - HERE          = .../orchestrator/scripts
  - OCH_DIR(..)   = .../telegram_bot/orchestrator   (.env 위치)
  - TG_DIR(../..) = .../telegram_bot                (orchestrator 패키지 import 경로)
"""
import os, sys, json
HERE = os.path.dirname(os.path.abspath(__file__))
OCH_DIR = os.path.dirname(HERE)              # telegram_bot/orchestrator
TG_DIR = os.path.dirname(OCH_DIR)            # telegram_bot
sys.path.insert(0, TG_DIR)

# 봇과 동일하게 orchestrator/.env 로드
envp = os.path.join(OCH_DIR, ".env")
if os.path.exists(envp):
    for line in open(envp):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

from orchestrator.telegram_io import TelegramIO
token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
_raw = (os.environ.get("TELEGRAM_ALLOWED_CHAT_IDS") or "").split(",")[0].strip()
if not token:
    raise SystemExit("TELEGRAM_BOT_TOKEN 없음")
if not _raw:
    raise SystemExit("TELEGRAM_ALLOWED_CHAT_IDS 없음 — 질문 보낼 대상 chat_id 를 지정하세요.")
chat_id = int(_raw)

text = sys.argv[1]
# 각 옵션 "라벨|callback_data" → 버튼 1열씩
# callback_data 는 "ask|key|value" 형식. 빈 세그먼트(ask||value) 오타 방지.
kb = []
for arg in sys.argv[2:]:
    label, cb = arg.split("|", 1)
    segs = cb.split("|")
    if any(s == "" for s in segs):
        raise SystemExit(f"callback_data 빈 세그먼트 오류: '{cb}' (ask|key|value 형식, || 금지)")
    kb.append([{"text": label, "callback_data": cb}])

tg = TelegramIO(token)
r = tg.send_message_kb(chat_id, text, inline_keyboard=kb)
print("발송 ok:", r.get("ok", r))
