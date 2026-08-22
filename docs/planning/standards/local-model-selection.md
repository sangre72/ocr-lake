# 로컬 모델 선정 — AI 구조화 파싱(structurer.py)

## 실측 환경
- macOS arm64(Apple Silicon), 시스템 메모리 48GB(`sysctl hw.memsize` 실측)

## 런타임: MLX (Ollama에서 전환 — 유저 지시 2026-08-22)

> 유저: "모델 구동은 가능하면 네이티브로 가장 빠르고 성능이 좋은 구동 방법으로 진행하도록 해. 올라마는 좀 느리더라."

- **1차 구현**: Ollama(`ollama pull qwen2.5:7b-instruct`, REST API 호출)로 실구현·검증까지 완료했었음.
- **전환 이유**: Ollama는 llama.cpp 기반 범용 러너라 Apple Silicon에서 추가 추상화 오버헤드가 있다.
  **MLX**(Apple이 자사 실리콘 전용으로 만든 프레임워크, `mlx-lm`)는 Metal 가속과 unified memory를
  직접 겨냥해 설계돼 M시리즈 칩에서 체감 속도가 더 빠르다(유저 실사용 체감 + 일반적으로 알려진 특성).
- **패키지**: `mlx-lm`(pip, 이미 설치돼 있었음 — network-budget.md 준수, 추가 설치 없이 재사용).
- **모델**: `mlx-community/Qwen2.5-7B-Instruct-4bit`(4bit 양자화, huggingface에서 자동 다운로드,
  Ollama용 qwen2.5:7b-instruct와 동급 파라미터 수·양자화 비트수).
  - mlx-community 배포판은 이미 MLX 포맷으로 변환·양자화가 완료돼 있어 별도 변환 작업 없이 바로
    `mlx_lm.load()`로 로드 가능(변환 오버헤드 없음, network-budget 측면에서도 유리).
  - 48GB 통합메모리에서 여유 있게 구동(4bit 7B ≈ 4~5GB 수준).
- **모듈 캐시**: 모델 로드가 무겁다(수십 초)는 점을 고려해 `core/ocr/structurer.py`에서 프로세스당 1회만
  로드해 전역 캐시(`_model`/`_tokenizer`)로 재사용하도록 구현(매 요청마다 재로드 방지).
- **실행 확인**: `structure_text()`를 실제 실행해 영수증(receipt)·일반(auto) 스키마 둘 다 정상 JSON 구조화 확인
  (아래 실행 검증 섹션 참고).

## 미채택 후보
- **Ollama(qwen2.5:7b-instruct)**: 1차로 실구현·검증까지 완료했으나 유저 지시로 MLX로 교체(네이티브 가속 우선).
- **Llama 3.1 8B**: 영어 중심 튜닝, 한국어 구조화 정확도가 Qwen2.5 대비 낮을 것으로 판단(리서치 기반 추정).
- **Qwen2.5-VL(비전)**: 이번 스코프(구조화 파싱)에는 불필요, §14-2(describer.py) 대상.
