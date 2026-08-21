#!/usr/bin/env bash
# 스카이워커 — 5초 감시 → stdout 이벤트 (monitor/에이전트 연동)
# line-buffered.
#   PENDING : 전환 즉시 + 5초마다 재알림 (요청 확인 핵심) ACTION=pick_up_now
#   WORKING : 전환 즉시 + 5초마다 재확인
#   IDLE    : 전환 시 1회만 stdout (에이전트 스팸 방지)
#             생존 하트비트는 poll5s → logs/worker1_events.log / 현황판 (5초)
# 내부 루프는 항상 sleep 5 — 요청 감지는 5초 주기.
set -euo pipefail
# 경로(u_136 이동): OCH_DIR(..)=telegram_bot/orchestrator(protocol), ROOT(../../..)=repo루트
SELF_DIR="$(cd "$(dirname "$0")" && pwd)"
OCH_DIR="$(cd "$SELF_DIR/.." && pwd)"
ROOT="$(cd "$SELF_DIR/../../.." && pwd)"
cd "$ROOT"
A_DIR="$OCH_DIR/protocol/a"
export PYTHONUNBUFFERED=1
if command -v stdbuf >/dev/null 2>&1; then
  if [[ -z "${WORKER1_STDBUF:-}" ]]; then
    export WORKER1_STDBUF=1
    exec stdbuf -oL -eL bash "$0" "$@"
  fi
fi
LAST_STATE=""
STALE_SEC="${WORKER1_STALE_SEC:-60}"
# PENDING/WORKING 동일 목록이어도 5초마다 재알림 (요청 확인 보장)
REMIND_SEC="${WORKER1_PENDING_REMIND_SEC:-5}"

emit() {
  printf '%s\n' "$*"
}

while true; do
  pending=""
  working=""
  now=$(date +%s)
  ts=$(date '+%H:%M:%S')

  shopt -s nullglob
  for f in "$A_DIR"/a_*.txt; do
    base=$(basename "$f")
    ar="$A_DIR/ar_${base#a_}"
    if [[ ! -f "$ar" ]]; then
      pending+="${base} "
      continue
    fi
    if grep -qE '\[STATUS\][[:space:]]*(done|blocked|error|needs-info|failed)' "$ar" 2>/dev/null; then
      continue
    fi
    if grep -qiE '\[STATUS\][[:space:]]*in[-_]?progress' "$ar" 2>/dev/null; then
      mtime=$(stat -f %m "$ar" 2>/dev/null || stat -c %Y "$ar" 2>/dev/null || echo "$now")
      age=$((now - mtime))
      if (( age >= STALE_SEC )); then
        pending+="${base}(stale:${age}s) "
      else
        working+="${base}(age:${age}s) "
      fi
    else
      pending+="${base}(unknown-status) "
    fi
  done
  shopt -u nullglob

  if [[ -n "$pending" ]]; then
    state="PENDING|${pending}"
    # 전환 즉시 + 동일 PENDING 유지 시 5초마다 재알림
    if [[ "$state" != "$LAST_STATE" ]] || (( now - ${LAST_EMIT:-0} >= REMIND_SEC )); then
      emit "WORKER1_PENDING ${ts} ${pending}ACTION=pick_up_now"
      LAST_STATE="$state"
      LAST_EMIT=$now
    fi
  elif [[ -n "$working" ]]; then
    state="WORKING|${working}"
    if [[ "$state" != "$LAST_STATE" ]] || (( now - ${LAST_EMIT:-0} >= REMIND_SEC )); then
      emit "WORKER1_WORKING ${ts} ${working}"
      LAST_STATE="$state"
      LAST_EMIT=$now
    fi
  else
    state="IDLE"
    # IDLE 전환 1회만 — 5초 폴링은 계속, stdout 스팸으로 요청 놓침 방지
    if [[ "$state" != "$LAST_STATE" ]]; then
      emit "WORKER1_IDLE ${ts} (poll=5s; heartbeat→logs/worker1_events.log)"
      LAST_STATE="$state"
      LAST_EMIT=$now
    fi
  fi

  sleep 5
done
