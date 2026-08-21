#!/usr/bin/env bash
# ocrlakebot 오케스트레이터 봇 파이프 관리 스크립트
# och.txt P0 규칙: 봇이 죽으면 즉시 되살린다. 이 스크립트가 status/start/stop/restart 를 제공.
#
# 사용(이동 후 — u_136 파이프 응집):
#   telegram_bot/orchestrator/scripts/start_orchestrator.sh status    # 생존 점검
#   telegram_bot/orchestrator/scripts/start_orchestrator.sh start     # 죽어 있으면 기동 (이미 떠 있으면 건드리지 않음)
#   telegram_bot/orchestrator/scripts/start_orchestrator.sh stop      # 정지
#   telegram_bot/orchestrator/scripts/start_orchestrator.sh restart   # 재기동
set -euo pipefail

# 이 스크립트: <repo>/telegram_bot/orchestrator/scripts/
# ../../.. = repo 루트(sky). 봇은 repo 루트를 cwd 로 기동해야 패키지 import(telegram_bot.orchestrator.*) 가 된다.
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$REPO_ROOT"

LOG_DIR="$REPO_ROOT/logs"
LOG_FILE="$LOG_DIR/orchestrator.log"
MODULE="telegram_bot.orchestrator.orchestrator"
PYTHON="${PYTHON:-python3}"

mkdir -p "$LOG_DIR"

# 이 repo에서 뜬 실제 파이썬 봇 프로세스의 PID 만 찾는다.
# (다른 경로의 동명 프로세스는 REPO_ROOT 로 걸러 제외. 감시 Monitor 스크립트(zsh/bash)가
#  자기 커맨드라인에 $MODULE 문자열을 그대로 담고 있어 pgrep -f 에 오탐되는 사고가 있었다 —
#  comm(실행 파일명)이 python 계열인 것만 취해 셸 스크립트 자기참조를 배제한다.)
find_pid() {
  pgrep -f "$MODULE" 2>/dev/null | while read -r pid; do
    comm="$(ps -p "$pid" -o comm= 2>/dev/null)"
    case "$comm" in
      *python*) ;;
      *) continue ;;
    esac
    # 프로세스의 cwd 가 이 repo 인지 확인 (lsof; 실패 시 그냥 통과)
    if lsof -a -p "$pid" -d cwd -Fn 2>/dev/null | grep -q "n$REPO_ROOT"; then
      echo "$pid"
    fi
  done | head -1
}

cmd_status() {
  local pid
  pid="$(find_pid || true)"
  if [ -n "${pid:-}" ]; then
    echo "✓ 봇 실행중 (PID $pid) @ocrlakebot"
    return 0
  else
    echo "✗ 봇 정지"
    return 1
  fi
}

cmd_start() {
  local pid
  pid="$(find_pid || true)"
  if [ -n "${pid:-}" ]; then
    echo "✓ 이미 실행중 (PID $pid) — 건드리지 않음"
    return 0
  fi
  echo "→ 봇 기동중..."
  PYTHONUNBUFFERED=1 nohup "$PYTHON" -u -m "$MODULE" >> "$LOG_FILE" 2>&1 &
  sleep 3
  if cmd_status; then
    echo "  로그: $LOG_FILE"
  else
    echo "✗ 기동 실패 — 로그 확인:"
    tail -20 "$LOG_FILE"
    return 1
  fi
}

cmd_stop() {
  local pid
  pid="$(find_pid || true)"
  if [ -z "${pid:-}" ]; then
    echo "이미 정지 상태"
    return 0
  fi
  kill "$pid" 2>/dev/null || true
  sleep 1
  echo "✓ 정지됨 (PID $pid)"
}

cmd_restart() {
  cmd_stop
  cmd_start
}

case "${1:-status}" in
  status)  cmd_status ;;
  start)   cmd_start ;;
  stop)    cmd_stop ;;
  restart) cmd_restart ;;
  *) echo "사용법: $0 {status|start|stop|restart}"; exit 2 ;;
esac
