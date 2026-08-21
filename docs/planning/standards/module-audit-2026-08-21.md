# 모듈 감사 — .claude/rules 표준 준수 실측 점검 (2026-08-21)

> 실측 근거: `find`/`wc -l`/`grep` 직접 실행 결과. 추측 없음(och.txt §11.5 규칙 A 준수).
> 점검 시점 기준 telegram_bot/pdf/, telegram_bot/video/ 등 일부 모듈은 병렬 작업(a_04)이 진행 중이었음 — 해당 파일은 관찰만 하고 수정하지 않음.

## 요약

| 항목 | 결과 | 위반 건수 |
|---|---|---|
| 1. 파일 라인수(§3-1) | ⚠ warn | 300줄↑ 4건, 800줄↑ 0건 |
| 2. mock 격리(§1) | ✅ pass | 0건 |
| 3. 모듈 배치(§4) | ✅ pass | 0건 |
| 4. 보안(업로드검증·시크릿) | ✅ pass | 0건 |
| 5. naming camelCase | ✅ pass | 0건 |
| 6. 기능 일관성(feature-consistency) | ⚠ warn | 1건(P2) |
| 7. network-budget(의존성 실사용) | ✅ pass | 0건 |

**총 위반/경고: 2건 (P1 0건, P2 2건)** — 심각한 위반 없음.

---

## 1. code-structure.md §3-1 파일 라인수

실측 명령: `find telegram_bot web -name "*.py" -o -name "*.tsx" -o -name "*.ts" | xargs wc -l`
(node_modules, .next 제외)

### 300줄 이상 파일 (800줄 미만 — "caution/warning" 등급, 즉시 분할 의무는 아님)

| 파일 | 줄수 | 카테고리 | 설명 | 분할 계획 |
|---|---|---|---|---|
| telegram_bot/orchestrator/worker.py | 661 | LOGIC | 워커 세션 운용 로직(오케 인프라, 도메인 로직 아님) | code-structure.md 예외 — 인프라/오케 스크립트 성격. 필요시 후속 a_ 로 책임별 분리 검토 |
| telegram_bot/orchestrator/orchestrator.py | 587 | LOGIC | 오케스트레이터 메인 루프 | 상동 |
| telegram_bot/orchestrator/protocol_store.py | 328 | LOGIC | protocol 파일 입출력·상태 정규화 | 300~500 구간(주의), 성장 추이 관찰만 필요 |
| telegram_bot/storage/db.py | 146 | — | (참고: 300 미만, 위반 아님) | — |

**800줄 이상(§4 위반 대상): 0건.** 즉시 분할 강제 대상 없음.

**판단**: orchestrator/worker.py, orchestrator.py는 도메인 로직이 아니라 "봇 인프라 운용 스크립트" 성격이라 code-structure.md의 LOGIC/COMPONENT/DAL 엄격 상한 취지(도메인 로직 비대화 방지)와는 결이 다름. 다만 661/587줄은 §3-1 "500~800줄 warning — 분할 계획" 구간에 해당하므로 **후속 a_ 로 책임별 분리(예: 메시지 relay/세션 관리/프로토콜 감시를 별도 파일로) 검토를 권고**(P2, 즉시 조치 불요).

---

## 2. code-structure.md §1 mock 격리

실측: `grep -rn "mock|Mock|MOCK" telegram_bot web --include=*.py --include=*.ts --include=*.tsx` (node_modules/.next 제외)

**결과: 0건.** 컴포넌트/로직에 하드코딩된 mock 데이터 없음. 별도 `src/mocks/`류 디렉토리가 없는 이유는 이 프로젝트가 실제 SQLite DB(telegram_bot/storage/db.py)를 처음부터 사용해 mock 자체가 불필요했기 때문(실측: telegram_bot/storage/db.py가 startup부터 실 DB 초기화). **pass.**

---

## 3. code-structure.md §4 모듈 배치

실측: `ls telegram_bot/`, `find web -maxdepth 2 -type d`

```
telegram_bot/
  bot.py            — 텔레그램 Application 엔트리
  classify/         — 이미지 유형 분류(순수 로직)
  config.py         — 설정 로더
  handlers/         — 텔레그램 메시지 핸들러
  ocr/              — Tesseract OCR 엔진 + 구조화 스텁
  orchestrator/     — 워커/오케 인프라(이 프로젝트 특유의 개발 운영 계층)
  pdf/, video/       — (a_04 병렬작업, 관찰 시점 신설 확인)
  pipeline.py       — 분류→처리 분기 파이프라인
  storage/          — SQLite 영속화
  vision/           — 이미지 설명 스텁

web/
  backend/          — FastAPI(main.py 엔트리 + routes.py)
  frontend/         — Next.js(app/ components/ lib/)
```

**판단**: 각 모듈이 단일 책임으로 명확히 분리되어 있음(ocr≠classify≠pipeline≠storage≠vision). web/backend는 `main.py`(엔트리·CORS)/`routes.py`(핸들러)로 이미 분리되어 과설계·과소설계 어느 쪽도 아님. web/frontend는 `app/`(라우트)·`components/`(UI)·`lib/`(API클라이언트·타입) 표준 Next.js 구조를 따름. **pass.**

---

## 4. security-guideline.md

### 4-1. 업로드 파일 검증 일관성
실측: `grep -rn "ALLOWED_FORMATS" telegram_bot web --include=*.py`

- `telegram_bot/ocr/engine.py:15` — `ALLOWED_FORMATS = {"JPEG","PNG","WEBP","BMP","TIFF"}` 정의(단일 출처)
- `telegram_bot/classify/engine.py:36` — 재사용(import)
- `web/backend/routes.py:52` — 재사용(import)

**동일 상수를 telegram/web 양쪽이 import해서 쓰므로 검증 로직 중복·불일치 없음. pass.**

### 4-2. 시크릿 하드코딩
실측: `grep -rnE "TELEGRAM_BOT_TOKEN\s*=\s*[\"'][0-9]{6,}"` 및 `grep -rnE "(sk-|xox[bp]-|AIza|ghp_)[A-Za-z0-9_-]{10,}"` (소스코드 대상, node_modules 내 CSS 프로퍼티명 오탐 제외)

**결과: 실제 하드코딩된 토큰/키 0건.** `telegram_bot/config.py`는 `os.environ.get("TELEGRAM_BOT_TOKEN")`로만 로드(값 미설정 시 ValueError). **pass.**

---

## 5. naming-standard.md — camelCase 일관성

실측: `telegram_bot/storage/db.py` `record_to_dict()` vs `web/frontend/lib/types.ts` `OcrRecord` 대조.

| DB(snake_case) | API/프론트(camelCase) | 프론트 타입 일치 |
|---|---|---|
| created_at | createdAt | ✅ |
| image_path | imagePath | ✅ |
| extracted_text | extractedText | ✅ |
| structured_json | structuredJson | ✅ |
| chat_id | chatId | ✅ |

**필드 9개 전부 1:1 일치. pass.**

---

## 6. feature-consistency-guideline.md

### 6-1. 업로드 처리 경로 대칭성
실측: `grep -rn "process_image" telegram_bot/handlers/ocr_handlers.py web/backend/routes.py`

- `telegram_bot/handlers/ocr_handlers.py:58` — `await process_image(image_bytes, lang=config.ocr_lang)`
- `web/backend/routes.py:43` — `await process_image(image_bytes)`

**동일 파이프라인 함수를 공유하므로 분류/OCR 로직은 대칭. pass.**

### 6-2. ⚠ 비대칭 발견 — `structure_text`(AI 구조화) 기능
실측: `grep -rln "structure_text" telegram_bot web --include=*.py --include=*.ts --include=*.tsx`

결과: `telegram_bot/ocr/structurer.py`, `telegram_bot/handlers/ocr_handlers.py` 2곳만 히트. **웹 백엔드(web/backend/routes.py)·프론트(web/frontend)에는 `/structure` 명령에 대응하는 구조화 API/화면이 없음.**

- 텔레그램: `/structure` 명령으로 마지막 OCR 텍스트를 구조화 요청 가능(`structurer.py`는 아직 `StructurerNotConfiguredError` 스텁이라 실사용은 미동작이지만, **경로 자체는 존재**).
- 웹: 업로드 후 구조화를 요청할 API 엔드포인트도, 프론트 UI도 없음.

**판단: P2 경고.** 현재 `structure_text`가 스텁(미구현)이라 사용자 체감 기능 격차는 없지만, AI 모델이 연동되는 시점에 텔레그램만 구조화를 제공하고 웹은 못 하는 실제 비대칭이 즉시 발생한다. **후속 a_ 필요**(구조화 API `POST /api/records/{id}/structure` 신설 + 프론트 버튼 — 이번 작업 범위 아니므로 직접 구현하지 않음).

---

## 7. network-budget.md — 의존성 실사용 검증

실측: `requirements.txt` 각 패키지의 import 존재 여부(`grep -rl "import X" telegram_bot web`).

| 패키지 | import 모듈 | 실사용 확인 |
|---|---|---|
| python-telegram-bot | telegram | ✅ 12개 파일 |
| pytesseract | pytesseract | ✅ 2개 파일 |
| Pillow | PIL | ✅ 3개 파일 |
| python-dotenv | dotenv | ✅ 1개 파일(bot.py) |
| fastapi | fastapi | ✅ 2개 파일 |
| uvicorn | (CLI 실행기, 직접 import 없음) | ✅ `python3 -m uvicorn ...`로 실행(정상 패턴) |
| python-multipart | (FastAPI UploadFile 내부 의존성) | ✅ FastAPI가 런타임에 요구(정상 패턴, 직접 import 안 함) |
| pdf2image | pdf2image | ✅ telegram_bot/pdf/engine.py |
| opencv-python | cv2 | ✅ telegram_bot/video/engine.py |

**전 패키지 실사용 확인, 불필요 설치 없음. pass.**

`web/frontend/package.json` dependencies: `next`, `react`, `react-dom` 3개뿐(devDependencies 별도) — 과다 설치 없음. **pass.**

---

## 조치 필요 항목 (우선순위)

- **P2-1**: `telegram_bot/orchestrator/worker.py`(661줄)·`orchestrator.py`(587줄) — 500~800줄 구간, 당장 위반은 아니나 책임별 분리 검토 권고. 후속 a_ 필요.
- **P2-2**: 웹(`web/backend`, `web/frontend`)에 `structure_text`(AI 구조화) 대응 기능 없음 — AI 비전/구조화 모델 연동 시점에 함께 웹 API/UI 추가 필요. 후속 a_ 필요.

P1(즉시 조치 필요) 위반 없음.
