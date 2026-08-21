#!/usr/bin/env bash
# 스카이워커 진행판 — protocol/a 와 ar 를 읽어 사람이 읽는 텍스트로 출력
# 사용: bash scripts/worker1_board.sh
# 출력: logs/WORKER_LIVE.txt + web/public/worker-status.txt (브라우저 http://localhost:3100/worker-status.txt)
set -euo pipefail
# 경로(u_136 이동): OCH_DIR(..)=telegram_bot/orchestrator(protocol), ROOT(../../..)=repo루트(logs/web)
SELF_DIR="$(cd "$(dirname "$0")" && pwd)"
OCH_DIR="$(cd "$SELF_DIR/.." && pwd)"
ROOT="$(cd "$SELF_DIR/../../.." && pwd)"
cd "$ROOT"
mkdir -p logs web/public
PROTO="$OCH_DIR/protocol"

OUT_LOG=logs/WORKER_LIVE.txt
OUT_WEB=web/public/worker-status.txt
ts=$(date '+%Y-%m-%d %H:%M:%S')

{
  echo "========================================"
  echo " 스카이워커 작업 현황판"
  echo " 갱신: $ts"
  echo "========================================"
  echo

  # poll status
  if [[ -f logs/worker1_status.txt ]]; then
    echo "[폴러 5초]"
    cat logs/worker1_status.txt
    echo
  fi

  shopt -s nullglob
  as=("$PROTO"/a/a_*.txt)
  if ((${#as[@]} == 0)); then
    echo "[현재 작업] 없음 — IDLE (신규 지시 대기)"
    echo
  else
    echo "[현재 큐] ${#as[@]}건"
    echo
    for a in "${as[@]}"; do
      base=$(basename "$a")
      nn=${base#a_}
      ar="$PROTO/a/ar_$nn"
      title=$(grep -E '^\[TITLE\]' "$a" 2>/dev/null | sed 's/\[TITLE\][[:space:]]*//' || echo "$base")
      echo "----------------------------------------"
      echo "지시: $base"
      echo "제목: $title"
      if [[ -f "$ar" ]]; then
        status=$(grep -E '^\[STATUS\]' "$ar" 2>/dev/null | head -1 | sed 's/\[STATUS\][[:space:]]*//')
        hb=$(grep -E '^\[HEARTBEAT\]' "$ar" 2>/dev/null | head -1 | sed 's/\[HEARTBEAT\][[:space:]]*//')
        updated=$(grep -E '^\[UPDATED\]' "$ar" 2>/dev/null | head -1 | sed 's/\[UPDATED\][[:space:]]*//')
        worker=$(grep -E '^\[WORKER\]' "$ar" 2>/dev/null | head -1 | sed 's/\[WORKER\][[:space:]]*//')
        echo "상태: ${status:-?}"
        echo "워커: ${worker:-?}"
        echo "하트비트: ${hb:-없음}"
        echo "갱신: ${updated:-?}"
        echo
        echo "--- ar 본문 (진행 내용) ---"
        # skip header tags, show body
        sed -n '/^## /,$p' "$ar" | head -40
        echo
      else
        echo "상태: (ar 없음 — 워커 미착수)"
        echo
      fi
    done
  fi

  echo "----------------------------------------"
  echo "[최근 완료] protocol/done/ar_* (최신 5)"
  ls -t "$PROTO"/done/ar_*.txt 2>/dev/null | head -5 | while read -r f; do
    st=$(grep -E '^\[STATUS\]' "$f" 2>/dev/null | head -1 | sed 's/\[STATUS\][[:space:]]*//')
    echo "  $(basename "$f")  [$st]"
  done
  echo
  echo "브라우저: http://localhost:3100/worker-status.txt"
  echo "로컬파일: logs/WORKER_LIVE.txt"
  echo "========================================"
} | tee "$OUT_LOG" > "$OUT_WEB"

# also print to stdout when run interactively
cat "$OUT_LOG"
