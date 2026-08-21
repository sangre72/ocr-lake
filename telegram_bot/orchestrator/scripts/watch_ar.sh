#!/usr/bin/env bash
# ar_* 5초 모니터 (och.txt §9-1). bash 3.2 호환, 한글 파일명 안전.
# 감시 대상 SEQ 를 인자로 받아, 그 ar_{SEQ} 가 종결(done/failed/error/blocked/needs-info)되거나
# protocol/a 에서 사라져 done/ 으로 아카이브되면 ★감지 후 종료.
# 봇이 done 을 즉시 아카이브해도 놓치지 않도록 protocol/a + protocol/done 양쪽을 본다.
# 사용: scripts/watch_ar.sh <SEQ> [최대초=1800]   예: scripts/watch_ar.sh 12
# 경로(u_136 이동): protocol = telegram_bot/orchestrator/protocol
SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROTO="$(cd "$SELF_DIR/.." && pwd)/protocol"
SEQ="$1"
MAX=${2:-1800}
[ -z "$SEQ" ] && { echo "사용법: watch_ar.sh <SEQ> [최대초]"; exit 2; }
SEQ2=$(printf '%02d' "$SEQ" 2>/dev/null || echo "$SEQ")
SPENT=0
PREV=""
while [ "$SPENT" -lt "$MAX" ]; do
  NOW=$(date '+%H:%M:%S')
  # protocol/a 에서 진행중 파일 찾기
  AF=$(find "$PROTO/a" -name "ar_${SEQ2}_*.txt" 2>/dev/null | head -1)
  DF=$(find "$PROTO/done" -name "ar_${SEQ2}_*.txt" 2>/dev/null | head -1)

  if [ -n "$DF" ]; then
    st=$(grep -m1 '^\[STATUS\]' "$DF" | cut -d']' -f2 | tr -d ' ')
    echo "[$NOW] ★ ar_${SEQ2} 종결·아카이브됨 (done/, STATUS=$st) — 오케 검증 필요."
    exit 0
  fi
  if [ -n "$AF" ]; then
    st=$(grep -m1 '^\[STATUS\]' "$AF" | cut -d']' -f2 | tr -d ' ')
    hb=$(grep -m1 '^\[HEARTBEAT\]' "$AF" | cut -d']' -f2-)
    CUR="$st|$hb"
    [ "$CUR" != "$PREV" ] && { echo "[$NOW] ar_${SEQ2} = $st | HB=$hb"; PREV="$CUR"; }
    case "$st" in
      done|failed|error|blocked|needs-info)
        echo "[$NOW] ★ ar_${SEQ2} 종결 감지 (STATUS=$st) — 오케 검증 필요."; exit 0 ;;
    esac
  else
    [ "$PREV" != "GONE" ] && { echo "[$NOW] ar_${SEQ2} 아직 미생성(워커 착수 대기)"; PREV="GONE"; }
  fi
  sleep 5
  SPENT=$((SPENT + 5))
done
echo "[모니터 종료 — ${MAX}s 경과, ar_${SEQ2} 종결 미감지]"
