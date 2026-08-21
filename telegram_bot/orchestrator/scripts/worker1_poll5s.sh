#!/usr/bin/env bash
# 스카이워커(worker_1) — protocol/a 5초 폴링
# 감지:
#  1) a_* 있고 대응 ar_* 없음 → PENDING
#  2) ar_* 가 있으나 종결 상태(done|blocked|error|needs-info|failed) 아님
#     이고 mtime 이 STALE_SEC(기본 180) 이상 → STALE (하트비트 정체)
set -euo pipefail
# 경로(u_136 이동): 이 스크립트=telegram_bot/orchestrator/scripts/
#  OCH_DIR(..)=telegram_bot/orchestrator(큐 protocol/), REPO_ROOT(../../..)=repo루트(logs/web)
SELF_DIR="$(cd "$(dirname "$0")" && pwd)"
OCH_DIR="$(cd "$SELF_DIR/.." && pwd)"
ROOT="$(cd "$SELF_DIR/../../.." && pwd)"   # repo 루트 (logs/, web/public 기준)
cd "$ROOT"
A_DIR="$OCH_DIR/protocol/a"
mkdir -p logs
STATUS=logs/worker1_status.txt
EVENTS=logs/worker1_events.log
PENDING=logs/worker1_pending.flag
LAST_MODE=""   # PENDING|WORKING|IDLE — 전이 로그용
LAST_SIG=""
STALE_SEC="${WORKER1_STALE_SEC:-180}"
echo $$ > logs/worker1_poll.pid
echo "[$(date '+%Y-%m-%d %H:%M:%S')] poll5s start pid=$$ stale=${STALE_SEC}s remind=5s" >> "$EVENTS"

while true; do
  pending_list=""
  now=$(date +%s)
  shopt -s nullglob
  for f in "$A_DIR"/a_*.txt; do
    base=$(basename "$f")
    ar="$A_DIR/ar_${base#a_}"
    if [[ ! -f "$ar" ]]; then
      pending_list+="${base}"$'\n'
      continue
    fi
    if grep -qE '\[STATUS\][[:space:]]*(done|blocked|error|needs-info|failed)' "$ar" 2>/dev/null; then
      continue
    fi
    # in-progress / 기타 미종결
    mtime=$(stat -f %m "$ar" 2>/dev/null || stat -c %Y "$ar" 2>/dev/null || echo "$now")
    age=$((now - mtime))
    if (( age >= STALE_SEC )); then
      pending_list+="${base}(stale:${age}s)"$'\n'
    fi
  done
  shopt -u nullglob

  ts=$(date '+%Y-%m-%d %H:%M:%S')
  if [[ -n "$pending_list" ]]; then
    {
      echo "[$ts] PENDING"
      printf '%s' "$pending_list"
    } > "$STATUS"
    printf '%s' "$pending_list" > "$PENDING"
    # stale age 가 초마다 바뀌어도 재알림 간격은 파일 베이스명만 본다
    sig=$(printf '%s' "$pending_list" | sed -E 's/\(stale:[0-9]+s\)//g' | tr '\n' '|')
    # 목록 변화 시 즉시 + 동일 PENDING 유지여도 5초마다 재기록
    if [[ "$sig" != "$LAST_SIG" ]] || (( now - ${LAST_PENDING_LOG:-0} >= 5 )); then
      echo "[$ts] PENDING: $(echo "$pending_list" | tr '\n' ' ')" >> "$EVENTS"
      LAST_SIG="$sig"
      LAST_PENDING_LOG=$now
    fi
    LAST_MODE="PENDING"
  else
    # ar 는 있지만 in-progress 인 건 작업 중으로 표기
    working=""
    shopt -s nullglob
    for f in "$A_DIR"/a_*.txt; do
      base=$(basename "$f")
      ar="$A_DIR/ar_${base#a_}"
      if [[ -f "$ar" ]] && grep -qiE '\[STATUS\][[:space:]]*in[-_]?progress' "$ar" 2>/dev/null; then
        working+="${base}"$'\n'
      fi
    done
    shopt -u nullglob
    if [[ -n "$working" ]]; then
      {
        echo "[$ts] IN-PROGRESS"
        printf '%s' "$working"
      } > "$STATUS"
      rm -f "$PENDING"
      # 모드 전이 시 1회 + WORKING 5초 재기록 (가시성)
      if [[ "$LAST_MODE" != "WORKING" ]] || (( now - ${LAST_PENDING_LOG:-0} >= 5 )); then
        echo "[$ts] WORKING: $(echo "$working" | tr '\n' ' ')" >> "$EVENTS"
        LAST_PENDING_LOG=$now
      fi
      LAST_MODE="WORKING"
      LAST_SIG=""
    else
      echo "[$ts] IDLE" > "$STATUS"
      rm -f "$PENDING"
      # IDLE 전이 1회 + 5초마다 TICK (events 에 생존 흔적)
      if [[ "$LAST_MODE" != "IDLE" ]]; then
        echo "[$ts] IDLE" >> "$EVENTS"
        LAST_PENDING_LOG=$now
      elif (( now - ${LAST_PENDING_LOG:-0} >= 5 )); then
        echo "[$ts] IDLE_TICK alive" >> "$EVENTS"
        LAST_PENDING_LOG=$now
      fi
      LAST_MODE="IDLE"
      LAST_SIG=""
    fi
  fi
  # 사람용 현황판 갱신 (logs + 브라우저 공개 txt)
  bash "$SELF_DIR/worker1_board.sh" >/dev/null 2>&1 || true
  sleep 5
done
