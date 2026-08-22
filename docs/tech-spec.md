# ocr-lake 기술 스펙

> 실측 기반 작성(코드 직접 확인). "구현됨"/"계획" 배지로 현재 상태와 로드맵을 구분한다.

## 아키텍처 개요

```
core/                채널 무관 핵심 로직
telegram_bot/        텔레그램 채널 어댑터 + 오케스트레이터 운영 인프라
web/backend/         FastAPI(core/ 를 참조)
web/frontend/        Next.js
```

`web/backend`·`telegram_bot/handlers`는 둘 다 `core/` 를 참조하는 대칭 구조다(채널마다 core 파이프라인을 재사용, 로직 중복 없음).

---

## 1. 현재 구현된 것 `[구현됨]`

### 1.1 이미지 유형 분류 게이트 — `core/classify/engine.py`
Tesseract `image_to_data`의 단어별 confidence·인식 단어 수로 판별.

| 판정 | 조건 |
|---|---|
| `document` | 단어수 ≥5 그리고 평균confidence ≥60.0 |
| `photo` | 단어수 ≤2 그리고 평균confidence ≤40.0 |
| `ambiguous` | 그 외 |

### 1.2 OCR 엔진 — `core/ocr/engine.py`
- Tesseract 기반, `extract_text(image_bytes, lang="kor+eng")`.
- 지원 포맷: `JPEG, PNG, WEBP, BMP, TIFF`(그 외 `UnsupportedImageError`).

### 1.3 PDF 처리 — `core/pdf/engine.py`
- `pdf2image`(poppler)로 페이지별 PNG 렌더링(200dpi, 최대 30페이지) → 각 페이지를 `core.pipeline.process_image`에 그대로 태움(로직 재사용, 재발명 없음).
- 페이지 안의 스캔된 서명·손글씨는 페이지 전체를 이미지로 취급하는 것으로 자동 커버 — 별도 임베디드-이미지(XObject) 추출은 하지 않음.

### 1.4 동영상 처리 — `core/video/engine.py`
- OpenCV로 기본 2.5초 간격, 최대 30프레임 샘플링 → 프레임마다 `process_image` 재사용.
- `route`가 `document`/`ambiguous_ocr`이고 텍스트가 있는 프레임만 결과에 남김(사물/배경 프레임 스킵).

### 1.5 분기 파이프라인 — `core/pipeline.py`
`process_image()` 라우팅: `document`→OCR / `photo`→이미지설명(스텁) / `ambiguous`→OCR 우선시도 후 10자 미만이면 설명 폴백.

| route | 의미 |
|---|---|
| `document` | 문서로 분류, OCR 텍스트 있음 |
| `photo` | 사진으로 분류, 설명 스텁 |
| `ambiguous_ocr` | 애매했으나 OCR 텍스트 확보 |
| `ambiguous_photo` | 애매했고 텍스트 부족, 설명 폴백 |
| `pdf_document` | PDF 처리 결과(라우트 레벨 상위값) |
| `video_frames` | 동영상 처리 결과 |

### 1.6 저장소 — `core/storage/db.py`
SQLite(`data/ocr_lake.db`), 테이블 `ocr_records`:

| 컬럼 | 타입 | 비고 |
|---|---|---|
| id | INTEGER PK | |
| created_at | TEXT | 기본값 now |
| source | TEXT | `telegram` \| `web` |
| image_path | TEXT | |
| route | TEXT | 위 route 값들 |
| extracted_text | TEXT | |
| description | TEXT | |
| structured_json | TEXT | JSON 직렬화 |
| chat_id | INTEGER | 텔레그램 발신자(웹은 null) |

DB 스네이크케이스 ↔ API/프론트 camelCase 변환은 `record_to_dict()`가 담당(naming-standard.md).

### 1.7 텔레그램 봇 — `telegram_bot/`
- 명령: `/start`, `/structure`(마지막 OCR 텍스트 구조화 — 현재 스텁 에러 반환).
- 메시지 핸들러: 사진/이미지문서 → `handle_photo`, PDF → `handle_pdf`, 동영상 → `handle_video`.

### 1.8 웹 API — `web/backend/routes.py`
| Method | Path | 설명 |
|---|---|---|
| POST | `/api/upload` | content-type으로 이미지/PDF/동영상 분기 처리 후 DB 저장, 레코드 반환 |
| GET | `/api/records?page=&size=` | 이력 목록(페이징) |
| GET | `/api/records/{id}` | 상세 조회 |
| GET | `/api/health` | 헬스체크 |

업로드 크기 상한: 이미지/PDF 20MB, 동영상 100MB. 저장 파일명은 서버 uuid4 랜덤 생성(원본 파일명 미신뢰).

### 1.9 웹 프론트 — `web/frontend/app/`
| Route | 화면 |
|---|---|
| `/` | 업로드(드래그앤드롭, 결과 표시) |
| `/records` | 이력 목록 |
| `/records/[id]` | 상세 조회 |

### 1.10 오케스트레이터 인프라 — `telegram_bot/orchestrator/`
`och.txt` 규약: 텔레그램 요청(`u_*.txt`) → 오케(세션)가 정제 → 워커 지시서(`a_*.txt`) → 워커 응답(`ar_*.txt`) → 텔레그램 회신, 파일큐 기반 위임 구조. `kong-bot`(형제 프로젝트) 연동: §10-A(파일 pull), §10-B(자격증명 공유해 자동 push), §10-C(라이선스 정책).

### 1.11 구조화 AI `[스텁 — 미구현]`
- `core/ocr/structurer.py`(`structure_text`): 문서유형별(영수증/명함 등) 구조화 파싱 — AI 모델(Claude/GPT) 미정, 호출 시 `StructurerNotConfiguredError`.
- `core/vision/describer.py`(`image_describe`): 이미지 설명(비전 모델) — 마찬가지로 미정, `DescriberNotConfiguredError`.

### 1.12 라이선스
`PolyForm Noncommercial License 1.0.0`(kong-bot과 동일 정책) — 개인/비상업 무료, 상업적 사용은 별도 유료 계약.

---

## 2. 앞으로 구현될 것(로드맵) `[계획]`

### 2.1 AI 구조화 파싱 `[계획]`
`structurer.py` 스텁을 실제 모델(Claude/GPT 등)로 구현. 모델 미정 — 별도 결정 필요.

### 2.2 이미지 설명(비전 모델) `[계획]`
`describer.py` 스텁 구현. 손글씨·사인·사물 사진처럼 OCR로 못 다루는 영역을 이 경로가 맡을 예정.

### 2.3 멀티 OCR 프로바이더(클라우드) 연동 `[계획]`
현재는 Tesseract 단일 엔진. 오늘 리서치(`docs/research/ocr-technology-trends.md`)에서 비교한 4개 클라우드 서비스를 선택적으로 연결하는 설계 방향:

| 서비스 | 리서치 근거 요약(원문 인용) |
|---|---|
| AWS Textract | "레이아웃 인지형 OCR, 표/키-값/체크박스까지 구조화 JSON 출력...복잡 문서·폼에서 높은 정확도" |
| Azure Document Intelligence | "사전학습 모델(영수증·송장·명함 등) 제공...표/폼 구조화 추출 최상위권, 2026 벤치마크에서 정확도 1위권" |
| Naver CLOVA OCR | "한국어·영어·일본어 특화, 영수증/사업자등록증 등 도메인 모델 제공...한글 필기체 인식 지원" |
| Google Cloud Vision API | "순수 텍스트 추출에 특화...처리 속도 최상위" |

**설계 방향**(구현 아님 — 계획 단계):
- **프로바이더 추상화 레이어**: `core/ocr/engine.py`의 `extract_text()`를 인터페이스로 일반화해, Tesseract를 기본 프로바이더로 두고 AWS Textract/Azure Document Intelligence/Naver CLOVA/Google Vision을 선택적으로 붙일 수 있는 provider 패턴으로 확장(예: `OcrProvider` 프로토콜 + `TesseractProvider`/`TextractProvider`/... 구현체).
- **폴백 트리거 지점**: `core/classify/engine.py`의 `ambiguous`/`photo` 분기(현재 Tesseract confidence가 낮게 나오는 지점)에서, 설정된 클라우드 프로바이더가 있으면 그쪽으로 재시도하는 옵션. 즉 "Tesseract confidence 낮음 → 클라우드 API 폴백"을 `core/pipeline.py`의 분기 로직에 자연스럽게 얹는 방향.
- **자격증명/비용 관리**: 각 클라우드 API 키(AWS/Azure/Naver/Google)를 `.env`에 프로바이더별로 등록, 사용자가 선택적으로 활성화(키 없으면 그 프로바이더 비활성 = Tesseract만 동작하는 현재 상태 그대로 유지). 클라우드 API는 비용이 발생하므로(리서치 문서에 페이지당 단가 비교 있음) 기본값은 off, 명시적 옵트인.
- 이 항목은 설계 방향 정리 단계이며, 실제 provider 인터페이스·클라우드 SDK 연동 코드는 아직 작성되지 않았다.

### 2.4 채널 확장(Discord/Slack) `[계획]`
현재 텔레그램만 구현. 아직 착수 전.

### 2.5 PDF 임베디드 이미지 별도 추출 `[계획 — 스코프 외 명시]`
현재는 페이지 전체 렌더링으로만 커버. PDF 내부 XObject(임베디드 이미지) 개별 파싱은 하지 않음(과설계 방지 목적으로 의도적 제외 — 필요성 재검토 시 별도 지시서).

### 2.6 kong-bot 자동 push 안정성 `[관찰 필요]`
§10-B(자격증명 공유해 kong-bot이 완료 시 자동으로 ocrlakebot API 호출)를 설정했으나, 실제 텔레그램 전송 성공 여부가 불확실했던 이력이 있음(§10-A-3 실측 기록 참고). 향후 재발 시 관찰 필요.
