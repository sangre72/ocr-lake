# ocr-lake 기술 스펙

> 실측 기반 문서(2026-08-22 시점 코드 실측). "구현됨" / "계획" 배지로 현재 상태와 로드맵을 명확히 구분한다.

## 목차

1. [아키텍처 개요](#1-아키텍처-개요)
2. [이미지 유형 분류 게이트](#2-이미지-유형-분류-게이트-구현됨)
3. [OCR 엔진](#3-ocr-엔진-구현됨)
4. [PDF 처리](#4-pdf-처리-구현됨)
5. [동영상 처리](#5-동영상-처리-구현됨)
6. [분기 파이프라인](#6-분기-파이프라인-구현됨)
7. [저장소(SQLite)](#7-저장소sqlite-구현됨)
8. [텔레그램 봇](#8-텔레그램-봇-구현됨)
9. [웹 API](#9-웹-apifastapi-구현됨)
10. [웹 프론트(Next.js)](#10-웹-프론트nextjs-구현됨)
11. [오케스트레이터 인프라](#11-오케스트레이터-인프라-구현됨)
12. [AI 구조화/비전 — 스텁 상태](#12-ai-구조화비전--스텁-상태-미구현)
13. [라이선스](#13-라이선스-구현됨)
14. [로드맵(앞으로 구현될 것)](#14-로드맵-앞으로-구현될-것)

---

## 1. 아키텍처 개요

`구현됨`

```
core/                채널 무관 핵심 로직(OCR·분류·PDF·동영상·저장소·파이프라인)
  ├─ classify/        이미지 유형 분류 게이트
  ├─ ocr/             Tesseract OCR 엔진 + 구조화 스텁
  ├─ pdf/             PDF → 페이지 이미지 렌더링
  ├─ video/           동영상 → 프레임 샘플링
  ├─ vision/          이미지 설명 스텁(비전 모델 미연동)
  ├─ storage/         SQLite 영속화
  └─ pipeline.py       분기 라우팅(document/photo/ambiguous_*)

telegram_bot/          텔레그램 채널 어댑터 + 오케스트레이터 인프라
  ├─ bot.py            Application 엔트리(polling)
  ├─ config.py         봇 설정(토큰 등)
  ├─ handlers/         텔레그램 메시지 → core 파이프라인 호출
  └─ orchestrator/      워커 위임 인프라(OCR 로직과 무관한 별도 관심사)

web/                   웹 채널
  ├─ backend/           FastAPI(core 파이프라인 호출)
  └─ frontend/          Next.js(App Router)
```

- **원칙**: `core/`는 어떤 입력 채널(텔레그램/웹/향후 Discord 등)에도 종속되지 않는다. `telegram_bot/handlers/`와
  `web/backend/routes.py`는 각자의 입력 형식(Telegram Update, HTTP UploadFile)을 bytes로 변환해 `core/`의
  동일 함수(`process_image`, `process_pdf`, `process_video`)를 호출하는 얇은 어댑터다.
- **검증(실측)**: `core/` 내부 상호 import는 전부 `from core.xxx import`, `telegram_bot/handlers/*.py`·
  `web/backend/*.py`는 `from core.xxx import`를 사용하며 옛 `from telegram_bot.{ocr,classify,pdf,video,vision,storage}`
  경로 참조는 0건(2026-08-22 grep 확인).

---

## 2. 이미지 유형 분류 게이트 `구현됨`

파일: `core/classify/engine.py`

```python
def classify_image(image_bytes: bytes, lang: str = "kor+eng") -> Literal["document", "photo", "ambiguous"]
```

**판정 로직**: Tesseract `image_to_data`로 단어별 confidence를 뽑아 (신뢰도 있는 단어 수, 평균 confidence)를
계산한 뒤 임계값으로 3분류한다.

| 상수 | 값 | 의미 |
|---|---|---|
| `_MIN_WORDS_FOR_DOCUMENT` | 5 | 이 이상 단어 수 + confidence 조건 만족 시 `document` |
| `_MIN_AVG_CONF_FOR_DOCUMENT` | 60.0 | document 판정 최소 평균 confidence |
| `_MAX_WORDS_FOR_PHOTO` | 2 | 이 이하 단어 수 + confidence 조건 만족 시 `photo` |
| `_MAX_AVG_CONF_FOR_PHOTO` | 40.0 | photo 판정 최대 평균 confidence |

- 위 두 조건 모두에 해당하지 않으면 `ambiguous`.
- 임계값은 코드 주석에 "실측(스모크 테스트)으로 조정된 값"으로 명시되어 있음 — 정밀 튜닝된 통계적 값은 아님.

---

## 3. OCR 엔진 `구현됨`

파일: `core/ocr/engine.py`

- Tesseract(`pytesseract.image_to_string`) 기반.
- **지원 포맷**(`ALLOWED_FORMATS`): `JPEG`, `PNG`, `WEBP`, `BMP`, `TIFF`.
- 기본 언어: `kor+eng`.
- `image.verify()` → 재오픈 → 포맷 검증 → RGB/L 모드 변환 후 OCR 수행.
- 지원 외 포맷·손상 이미지는 `UnsupportedImageError` 발생.

---

## 4. PDF 처리 `구현됨`

파일: `core/pdf/engine.py`

```python
async def process_pdf(pdf_bytes: bytes, lang: str = "kor+eng") -> PdfOcrResult
```

- `pdf2image.convert_from_bytes`(내부적으로 poppler 바이너리 사용)로 각 페이지를 PNG 이미지로 렌더링(dpi=200).
- 렌더링된 페이지 이미지를 **기존 `core.pipeline.process_image`에 그대로 재사용**(분류/OCR 로직 재구현 없음).
- 페이지 수 상한 `MAX_PDF_PAGES = 30`(초과 시 앞부분만 처리, 경고 로그).
- 결과: 페이지별 `PdfPageResult` 리스트 + `[페이지 N]\n텍스트` 형태로 이어붙인 `combined_text`.
- **PDF 내부 스캔 이미지/서명/손글씨**: 페이지 전체를 이미지로 렌더링하는 방식이라 자동으로 커버되지만,
  PDF 내부 XObject(임베디드 이미지) 개별 추출은 하지 않는다(스코프 제외, §14 로드맵 참고).

---

## 5. 동영상 처리 `구현됨`

파일: `core/video/engine.py`

```python
async def process_video(video_bytes, lang="kor+eng", sample_interval_sec=2.5, max_frames=30) -> VideoOcrResult
```

- OpenCV(`cv2.VideoCapture`)로 임시파일 기록 후 프레임 접근.
- 기본 샘플링 간격 `DEFAULT_SAMPLE_INTERVAL_SEC = 2.5`초, 최대 프레임 수 `MAX_FRAMES = 30`.
- 각 프레임을 `core.pipeline.process_image`에 재사용 호출.
- `document` 또는 `ambiguous_ocr`로 분류되고 텍스트가 있는 프레임만 `document_frames`에 채택,
  `photo` 판정 프레임은 스킵.
- 결과: 채택된 프레임 목록(`timestamp_sec` 포함) + 이어붙인 `combined_text`.
- 프레임별 처리 중 예외는 개별 프레임만 스킵(전체 실패로 전파하지 않음).

---

## 6. 분기 파이프라인 `구현됨`

파일: `core/pipeline.py`

```python
async def process_image(image_bytes: bytes, lang="kor+eng") -> PipelineResult
```

`PipelineResult(route, text, description, note)` — `route`는 다음 4종:

| route | 조건 | 내용 |
|---|---|---|
| `document` | classify=document | `extract_text()` 결과가 `text`에 채워짐 |
| `photo` | classify=photo | `image_describe()` 호출 시도 → 스텁이라 `note`에 미구현 메시지 |
| `ambiguous_ocr` | classify=ambiguous, OCR 텍스트≥10자(`AMBIGUOUS_OCR_MIN_CHARS`) | `text` 채워짐(OCR 채택) |
| `ambiguous_photo` | classify=ambiguous, OCR 텍스트<10자 | photo와 동일하게 describe 시도 → note |

- PDF/동영상 파이프라인이 이 함수를 그대로 재사용하므로, `route`는 저장소 스키마에서 `pdf_document`,
  `video_frames`로 별도 확장(§7 참고) — 페이지/프레임 단위의 개별 `route`는 `structured_json`에 기록.

---

## 7. 저장소(SQLite) `구현됨`

파일: `core/storage/db.py` — DB 경로: `data/ocr_lake.db`(레포 루트 기준, `.gitignore` 처리됨).

### `ocr_records` 테이블 (실측 스키마)

| 컬럼 | 타입 | 제약 | 설명 |
|---|---|---|---|
| `id` | INTEGER | PK AUTOINCREMENT | |
| `created_at` | TEXT | NOT NULL, DEFAULT now | |
| `source` | TEXT | NOT NULL, CHECK IN ('telegram','web') | 어느 채널에서 처리됐는지 |
| `image_path` | TEXT | nullable | 저장된 원본 파일 상대경로 |
| `route` | TEXT | NOT NULL, CHECK IN ('document','photo','ambiguous_ocr','ambiguous_photo','pdf_document','video_frames') | |
| `extracted_text` | TEXT | nullable | |
| `description` | TEXT | nullable | |
| `structured_json` | TEXT | nullable, JSON 직렬화 | PDF 페이지별/동영상 프레임별 상세 |
| `chat_id` | INTEGER | nullable | 텔레그램 발신 chat id(웹 경로는 null) |

- 인덱스: `idx_ocr_records_created_at`(`created_at DESC`).
- API/프론트 응답 시 `record_to_dict()`가 스네이크케이스 → camelCase 변환(naming-standard.md).

---

## 8. 텔레그램 봇 `구현됨`

파일: `telegram_bot/bot.py`, `telegram_bot/handlers/{ocr_handlers,pdf_video_handlers,common}.py`

### 명령
- `/start` — 사용 안내.
- `/structure` — 마지막 OCR 텍스트를 구조화(현재 스텁 → 미구현 메시지 반환, §12 참고).

### 메시지 핸들러(실측 — `build_application()` 등록 순)
| 핸들러 | 트리거 | 처리 |
|---|---|---|
| `handle_photo` | `filters.PHOTO \| filters.Document.IMAGE` | `core.pipeline.process_image` |
| `handle_pdf` | `filters.Document.PDF` | `core.pdf.process_pdf` |
| `handle_video` | `filters.VIDEO \| filters.Document.VIDEO` | `core.video.process_video` |

- 권한 체크: `is_allowed()`(`telegram_bot/handlers/common.py`) — `TELEGRAM_ALLOWED_CHAT_IDS` 설정 시 해당
  chat_id만 허용, 미설정 시 전체 허용.
- 파일 크기 제한: 이미지/PDF는 `config.max_image_size_mb`(기본 20MB), 동영상은 그 5배.
- 처리 결과는 `save_record_safely()`로 DB 저장(저장 실패해도 텔레그램 응답 흐름은 유지 — try/except 격리).

---

## 9. 웹 API(FastAPI) `구현됨`

파일: `web/backend/main.py`, `web/backend/routes.py`

| 메서드 | 경로 | 설명 |
|---|---|---|
| GET | `/api/health` | 헬스체크, `{"status":"ok"}` |
| POST | `/api/upload` | multipart 파일 업로드. `content_type`으로 이미지/PDF/동영상 자동 분기 |
| GET | `/api/records?page=&size=` | 이력 목록(페이징, 최신순) |
| GET | `/api/records/{id}` | 단건 상세(없으면 404) |

### `/api/upload` 응답 스키마(camelCase)
```json
{
  "id": 1, "createdAt": "2026-08-22 ...", "source": "web",
  "imagePath": "data/uploads/xxxx.png", "route": "document",
  "extractedText": "...", "description": null,
  "structuredJson": null, "chatId": null
}
```

### `/api/records` 응답
```json
{ "records": [ ...위 스키마... ], "total": 5, "page": 1, "size": 20 }
```

### 보안(실측)
- 이미지: PIL 재오픈 검증 + `ALLOWED_FORMATS` 화이트리스트.
- PDF: `application/pdf` content-type만 라우팅, `process_pdf` 자체 파싱 실패 시 400(위장 실행파일도 이 경로로 자동 차단).
- 동영상: `video/mp4`, `video/quicktime`, `video/webm`, `video/x-msvideo` content-type만 라우팅.
- 업로드 파일 저장명은 서버에서 `uuid4` 랜덤 생성(원본 파일명 미신뢰).
- 업로드 크기 상한: 이미지/PDF 20MB(`MAX_UPLOAD_BYTES`), 동영상 100MB(`MAX_VIDEO_BYTES`).
- CORS: `localhost:3000`, `localhost:3001`(및 127.0.0.1 동일)만 허용.

---

## 10. 웹 프론트(Next.js) `구현됨`

디렉토리: `web/frontend/`(App Router, TypeScript, Tailwind)

| 라우트 | 파일 | 기능 |
|---|---|---|
| `/` | `app/page.tsx` | 업로드 화면(`UploadCard`) — 드래그앤드롭/파일선택, 결과(텍스트 또는 사진/미구현 안내) 표시 |
| `/records` | `app/records/page.tsx` | 이력 목록(`RecordList`) — 테이블, 페이징 |
| `/records/[id]` | `app/records/[id]/page.tsx` | 이력 상세(`RecordDetail`) |

- `lib/api.ts`: 백엔드 API 클라이언트(`uploadImage`, `fetchRecords`, `fetchRecord`). `NEXT_PUBLIC_API_BASE`
  환경변수로 백엔드 주소 지정(기본 `http://localhost:8000`).
- `lib/types.ts`, `lib/route-label.ts`: `OcrRoute` 타입 및 라벨/배지 맵을 6종 route(document/photo/
  ambiguous_ocr/ambiguous_photo/pdf_document/video_frames) 전부에 대해 정의.
- 접근성: 시맨틱 마크업, `aria-live`(로딩/에러), 폼 label 연결. 375px 뷰포트 좌우 잘림 없음(Playwright 실측 확인).
- 디자인: CSS 변수 기반 토큰(`--radius-md`, `--info` 등), 카드/배지 컴포넌트 스타일.

---

## 11. 오케스트레이터 인프라 `구현됨`

디렉토리: `telegram_bot/orchestrator/`(OCR 로직과 무관한 별도 관심사 — 이 프로젝트를 운영하는 워크플로 인프라)

- **구조**: `protocol/u/`(유저 메시지 큐) → `protocol/a/`(오케스트레이터가 작성하는 지시서, `a_{NN}_{topic}.txt`)
  → 워커가 `ar_{NN}_{topic}.txt`로 응답 → 종결 시 `protocol/done/`으로 아카이브.
- **역할 분리**: 오케스트레이터(`och.txt` 역할 문서)는 유저 메시지 정제 + 지시서 작성 + 워커 관제만 담당,
  실무(코드 구현/조사)는 워커(`worker_1.txt` 역할, 본 문서 작성 주체)가 수행.
- **kong-bot 연동**(och.txt §10-A~C 실측 요약):
  - §10-A `SHARED_IN`: kong-bot(별도 프로젝트, `~/git/kong-bot`)이 발행하는 read-only manifest
    (`~/git/kong-bot/telegram_bot/orchestrator/shared_out/manifest.json`)를 ocr-lake가 pull 방식으로 참조.
    OCR 테스트 샘플(이미지/PDF 등) 확보에 사용(a_04에서 kong-bot 샘플 PDF 2건 실제 활용).
  - §10-B `OUTBOUND`: ocrlakebot 토큰을 kong-bot에 공유해, kong-bot이 작업 완료 시 ocrlakebot API로
    직접 결과물을 사용자에게 push하는 자동 전달 경로(수동 포워딩 대체).
  - §10-C: 라이선스 정책이 kong-bot과 동일(§13 참고).

---

## 12. AI 구조화/비전 — 스텁 상태 `미구현`

| 모듈 | 파일 | 현재 상태 |
|---|---|---|
| 텍스트 구조화 | `core/ocr/structurer.py` | `structure_text()` 호출 시 항상 `StructurerNotConfiguredError` 발생. AI 모델(Claude/GPT) 미연동. |
| 이미지 설명 | `core/vision/describer.py` | `image_describe()` 호출 시 항상 `DescriberNotConfiguredError` 발생. 비전 모델 미연동. |

- 두 스텁 모두 "모델 결정되면 이 모듈 안에서 SDK 호출부만 구현하면 되고, 호출부(pipeline/handlers)는
  변경 불요"하도록 인터페이스가 이미 고정되어 있음(코드 주석 확인).
- `pipeline.process_image`의 `photo`/`ambiguous_photo` 경로가 `image_describe()`를 호출하지만 스텁이라
  항상 `note`(미구현 안내 메시지)로 폴백 — **실제 이미지 설명 기능은 아직 사용자에게 제공되지 않음**.

---

## 13. 라이선스 `구현됨`

- `PolyForm Noncommercial License 1.0.0`(`./LICENSE`, kong-bot과 동일 조건 — och.txt §10-C).
- 개인/비영리 용도(연구·학습·취미·비영리·교육) 무료.
- 상업적 사용은 별도 유료 라이선스 계약 필요.

---

## 14. 로드맵(앞으로 구현될 것)

> 아래 항목은 전부 `계획` — 착수 전이거나 스텁 상태. 일정·모델 확정 없음.

### 14-1. AI 구조화 파싱 `계획`
- `core/ocr/structurer.py` 구현 — 영수증/명함 등 문서유형별 스키마 추출(예: 금액·날짜·상호명 필드화).
- 사용 모델(Claude/GPT 등) 미정. `ANTHROPIC_API_KEY`/`OPENAI_API_KEY` 설정 후 착수 예정(코드 주석 근거).

### 14-2. 이미지 설명(비전 모델) `계획`
- `core/vision/describer.py` 구현 — 손글씨/사인/사물 사진 등 OCR로 커버 안 되는 케이스를 비전 모델로 설명.
- classify_image의 저신뢰도 판정(photo/ambiguous)이 이 경로로 자연스럽게 폴백하도록 이미 설계되어 있어,
  모델만 붙이면 별도 라우팅 로직 변경 없이 활성화 가능(현재 검증된 구조).

### 14-3. 채널 확장(Discord/Slack) `계획`
- 현재 텔레그램 채널만 구현. `core/`가 채널 무관 구조로 분리되어 있어(§1) 신규 채널 어댑터 추가 시
  `core.pipeline.process_image` 등을 그대로 재사용 가능한 구조는 마련되어 있으나, 실제 어댑터 구현은
  아직 착수 전.

### 14-4. 멀티 클라우드 OCR 프로바이더 연동(AWS·Microsoft·Naver·Google) `계획`
- 현재는 Tesseract(로컬 오픈소스) 단일 엔진만 연동돼 있다(§3). 유저 요청으로 다음 4개 클라우드 OCR API 연동을
  로드맵에 추가한다 — 비교 근거는 이미 작성된 `docs/research/ocr-technology-trends.md` 참고(중복 리서치 불필요):
  - **AWS Textract**: 표/폼/키-값 구조화 추출에 강함. 복잡 문서(영수증·송장) 정확도 높음.
  - **Microsoft Azure Document Intelligence**(구 Form Recognizer): 사전학습 영수증/명함/송장 모델 제공,
    2026 벤치마크 기준 정확도 상위권.
  - **Naver CLOVA OCR**: 한국어·영수증/사업자등록증 등 국내 도메인 특화 모델, 한글 필기체 지원.
  - **Google Cloud Vision API**: 순수 텍스트 추출 속도 최상위, 비용 경쟁력.
- **설계 방향(제안, 미착수)**:
  1. `core/ocr/` 아래 provider 인터페이스 추상화(예: `OcrProvider` 프로토콜 — `extract_text(bytes, lang) -> str`
     또는 confidence 포함 구조화 반환) — 지금의 Tesseract 단일 함수 호출부(`core/ocr/engine.py`)를
     provider 중 하나로 승격, 나머지 클라우드 provider를 같은 인터페이스로 추가.
  2. **폴백 트리거**: `core/classify/engine.py`의 저신뢰도 판정(ambiguous/photo)에서 Tesseract 결과가
     불충분할 때, 설정된 클라우드 provider로 재시도하는 옵션(§파이프라인 확장, `core/pipeline.py`
     `_describe_or_note`류 분기에 준하는 방식).
  3. **자격증명 관리**: 각 클라우드 API 키(AWS/Azure/Naver/Google)는 `.env`에 provider별 키로 저장,
     설정 안 된 provider는 자동 비활성(현재 `structurer.py`/`describer.py`의 "미설정 시 스텁 에러" 패턴과 동일).
     사용자가 선택적으로 어떤 provider를 활성화할지 설정 가능하게.
  4. **비용 고려**: 클라우드 API는 건당 과금이므로, Tesseract로 충분한 케이스(고신뢰도 document)는 클라우드
     호출을 건너뛰어 비용 최소화(§계층형 파이프라인 아이디어, 오케스트레이터가 초기 설계 논의에서 제안한
     "confidence 기반 3단계 분기"와 일치하는 방향).
- 일정·우선순위 미정 — 착수 전.

### 14-5. PDF 내부 임베디드 이미지(XObject) 개별 추출 `계획 — 스코프 명시적 제외`
- 현재는 PDF 페이지 전체를 이미지로 렌더링하는 방식으로만 처리(§4). PDF 내부에 개별 삽입된 이미지
  객체(XObject)를 따로 파싱해 추출하는 기능은 a_04 지시서에서 "과설계 방지" 이유로 명시적으로
  스코프 제외됨. 필요성이 확인되면 별도 작업으로 검토.

### 14-6. kong-bot 자동 push 안정성 `관찰 필요`
- och.txt §10-B의 자동 push 경로(kong-bot이 ocrlakebot API로 직접 결과 전달)가 과거 한 차례 전달
  실패 사례가 있었음(§10-A-3의 정정 기록 — 원인은 봇-봇 DM 차단이 아니라 다른 요인으로 추정, 확정 원인
  미규명). 현재는 manifest pull(§10-A)이 폴백 경로로 병행 운영 중. 재발 시 원인 규명 필요.
