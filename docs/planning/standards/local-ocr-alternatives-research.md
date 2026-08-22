# Tesseract 대비 로컬 OCR 대안 리서치 + 실측 비교 (2026-08-22)

> 실측 기반. 리서치만으로 결론 내지 않음(RAG 실패 교훈 준수) — 실행 가능한 후보는 전부 같은 이미지로
> 직접 실행해 비교했다. 로컬 실행 불가능한 것(국내 VL 모델)은 실행 없이 벤치마크 근거만 전달한다.

## 1. 실측 비교 — Tesseract vs Qwen2.5-VL(mlx-vlm, 이미 로드됨)

### 케이스 A: 다국어 팬그램 텍스트 사진(kong-bot photos_02.tif)

| 엔진 | 처리시간 | 결과 |
|---|---|---|
| Tesseract | 0.64s | `Der ,.schnelle" braune Fuchs springt / iiber den faulen Hund. ... marron rapido ... preguicoso.` — **오류 다수**(über→iiber, marrón→marron 악센트 소실, "o cão"→"0 080" 완전 오인식) |
| Qwen2.5-VL(mlx-vlm) | 4.14s | `Der „schnelle" braune Fuchs springt / über den faulen Hund. ... marrón rápido ... preguiçoso.` — **전부 정확**(악센트·특수문자 완벽 보존) |

### 케이스 B: 한글 텍스트(직접 생성 — 안내문+가격+전화번호)

| 엔진 | 처리시간 | 결과 |
|---|---|---|
| Tesseract | 0.24s | `안녕하세요 이것은 한글 테스트입니다.\n가격: 12,345원 (부가세 포함)\n전화번호: 010-1234-5678` — **완벽** |
| Qwen2.5-VL(mlx-vlm) | 0.99s | 동일 결과 — **완벽** |

### 결론 (실측 기반)
- **한글 인쇄체는 Tesseract로 이미 충분**(케이스 B 완벽 일치, 4배 더 빠름).
- **비ASCII 특수문자(유럽어 악센트·세디유 등)가 섞인 텍스트는 Qwen2.5-VL이 확실히 우수**(케이스 A).
- Qwen2.5-VL은 **이미 로드돼 있어(비전 설명 기능과 공유) 신규 다운로드 0** — network-budget 효율적.
- **제안**: 지금 당장 Tesseract를 교체하지 말 것. 대신 `core/ocr/provider_base.py`(§14-4에서 만든 provider
  추상화)에 "mlx_vlm_ocr_provider"를 하나 더 추가해, **Tesseract confidence가 낮은 ambiguous 케이스에서만
  Qwen2.5-VL로 폴백**하는 하이브리드 구성을 제안(이미 있는 confidence 기반 분기 구조 그대로 재사용 가능).
  전면 교체가 아니라 **재사용 가능한 폴백 옵션 추가**가 실측 근거상 합리적.

## 2. 미실행 리서치 — PaddleOCR / EasyOCR / docTR

이 레포에 셋 다 미설치(실측: `import` 전부 `ModuleNotFoundError`). 설치 전 벤치마크만 조사:

- **PaddleOCR**: 한중일(CJK) 특화 학습으로 한국어 인식에서 강점이 있다는 2026 벤치마크 존재
  ([koncile.ai](https://www.koncile.ai/en/ressources/paddleocr-analyse-avantages-alternatives-open-source),
  [codesota.com](https://www.codesota.com/ocr/paddleocr-vs-tesseract)) — "PaddleOCR-VL-1.5(2026-01)가
  OmniDocBench v1.5에서 94.5% 정확도, 109개 언어 지원"(codesota.com 기사 인용).
- **Tesseract**: CPU 전용 최소 풋프린트(10MB, 0.77s) 강점 — 이미 이 프로젝트가 쓰는 이유와 일치
  ([codesota.com](https://www.codesota.com/ocr/paddleocr-vs-tesseract)).
- **판단**: 케이스 B(한글 인쇄체) 실측에서 이미 Tesseract가 완벽했으므로, PaddleOCR 설치(수백MB급 모델
  다운로드 추정)까지 감수할 실측 근거는 약하다. **설치·비교는 보류** — 향후 실제 한글 필기체·저품질
  스캔본에서 Tesseract 오류가 반복 확인되면 그때 재검토 권장.

## 3. 국내(한국) VL/멀티모달 모델 — 로컬 실행 가능성 확인

유저 질문: "한국 VL 모델이나 LLM 모델은 아마도 vision 쪽이 평가가 나쁘겠지?" — 추측 없이 확인.

### 실측 확인 결과
- **HyperCLOVA X 8B Omni**(네이버): HuggingFace 모델 카드·논문상 "Korean-centric multimodal capabilities...
  high-density OCR"에 특화 학습됐다고 명시([arxiv.org/abs/2601.01792](https://arxiv.org/html/2601.01792v1)) —
  **벤치마크 근거상 한국어 OCR/비전 성능은 나쁘지 않고 오히려 특화됨**(유저 추측과 반대).
  단, **mlx-community 검색 결과 0건**(HuggingFace API 직접 조회) — **로컬 MLX 실행 불가**, 실측 비교 불가.
- **LG EXAONE**: mlx-community에 `EXAONE-3.5-2.4B-Instruct`(4bit/6bit/8bit/bf16) 존재하나 **텍스트 전용
  모델**(태그에 vision/image 관련 태그 없음, 아키텍처 `exaone` — 순수 언어모델). **비전 지원 EXAONE 계열은
  mlx-community에서 확인되지 않음** — 실측 비교 불가.
- **결론**: 국내 VL 모델 자체의 벤치마크 평가가 나쁜 게 아니라(HyperCLOVA X는 오히려 한국어 OCR 특화),
  **로컬(MLX) 오프라인 실행 가능한 포팅판이 아직 없어서** 이 프로젝트에서 실측 비교 자체가 불가능한
  상황이다. 유저의 "평가가 나쁘겠지"라는 추측은 근거상 확인되지 않음 — 오히려 특화 학습됐다는 근거가
  있으나, 접근 경로(로컬 실행)가 없어 활용 불가.
- 클라우드 API 경유라면(§14-4 이미 다룸) 네이버 CLOVA OCR로 접근 가능하나, 이건 "로컬" 조건에 안 맞음.

## 최종 제안 요약
1. **당장 교체 안 함**(한글은 Tesseract로 충분, 실측 확인).
2. Qwen2.5-VL을 Tesseract 저신뢰도 폴백 provider로 추가하는 건 향후 검토 가치 있음(신규 다운로드 0).
3. PaddleOCR 등 신규 설치는 실제 문제(한글 필기체·저품질 스캔 실패 사례)가 쌓이면 재검토.
4. 국내 VL 모델(HyperCLOVA X)은 로컬 실행 경로가 없어 현재는 활용 불가 — mlx-community 포팅을 주기적으로
   재확인할 가치는 있음(오늘 기준 0건).
