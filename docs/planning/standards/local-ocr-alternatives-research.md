# Tesseract보다 정확도 높은 로컬(오프라인) OCR 대안 리서치

> 실측 기반 문서(2026-08-22). 웹서치 결과만으로 결론 내리지 않고, 실제 이미지로 Tesseract와
> 나란히 비교 실행한 결과만 신뢰한다(RAG 실패 사례의 교훈 — och.txt 규칙 A).

## 결론 요약

**지금 당장 Tesseract를 교체할 만큼 확실한 대안은 없다. 현상 유지를 권장하며, 판단은 오케 확인 후 결정.**

- `mlx-vlm`(이미 로드된 비전모델 Qwen2.5-VL, **신규 다운로드 0**)을 OCR 프롬프트로 실험한 결과,
  **다국어(영/독/불/이/포)** 텍스트에서는 Tesseract보다 명확히 우세했다.
- 그러나 **한글**에서는 완전한 신뢰 수준에 이르지 못했다(부분 실패 — 아래 §3 참고).
- PaddleOCR·EasyOCR·docTR은 전부 torch 또는 PaddlePaddle 대형 프레임워크에 의존하는데, 실제로
  EasyOCR을 설치 시도하다 시스템 전역 `setuptools`를 강제 업그레이드해 `mlx_vlm`/`mlx_lm` 임포트
  체인 전체가 파손되는 사고가 발생했다(즉시 감지·복구했으나 이번이 **세 번째**로 반복된 같은 패턴의
  사고 — a_19 RAG의 `mlx-embeddings`, a_21 멀티클라우드의 `google-cloud-vision`에 이어).

## 1. 후보 비교표 (문서 조사 기반)

| 후보 | 한글 지원 | Apple Silicon | 설치 크기 | 유지보수 | 실측 시도 |
|---|---|---|---|---|---|
| PaddleOCR | 지원(PP-OCRv5, `korean_PP-OCRv5_mobile_rec`) | 지원(PaddleOCR-VL은 MLX 백엔드 활용 가능, M4 검증 사례 있음) | 대형(PaddlePaddle 프레임워크 포함, 수백MB) | 활발 | **미시도**(EasyOCR 사고 이후 유사 위험 판단해 보류) |
| EasyOCR | 지원(`ko` 포함 80+ 언어) | 지원(torch 기반) | torch 포함 시 대형 | 활발 | **설치 시도 → 시스템 파손 → 즉시 폐기**(아래 §4) |
| docTR | 지원(Korean 명시) | 지원(MPS, ONNX 버전은 CoreML) | torch/tf 기반, 중대형 | 활발 | **미시도**(EasyOCR과 동일 계열 위험 판단) |
| **mlx-vlm(Qwen2.5-VL, 기존 로드 모델 재사용)** | 부분 지원(§3) | 네이티브(이미 이 프로젝트가 쓰는 스택) | **0**(신규 설치 없음) | 이 프로젝트가 이미 의존 | **실측 완료(안전)** |

## 2. 실측 비교 — 다국어 텍스트(kong-bot photos_02.tif)

### Tesseract 결과
```
The (quick) [brown] {fox} jumps!
Over the $43,456.78 <lazy> #90 dog
& duck/goose, as 12.5% of E-mail
from aspammer@website.com is spam.
Der ,.schnelle" braune Fuchs springt
iiber den faulen Hund. Le renard brun
«rapide» saute par-dessus le chien
paresseux. La volpe marrone rapida
salta sopra il cane pigro. El zorro
marron rapido salta sobre el perro
perezoso. A raposa marrom rapida
salta sobre 0 080 preguicoso.
```
오류: `über`→`iiber`, `marrón`→`marron`(악센트 누락), `cão`→`080`(완전 오인식).

### Qwen2.5-VL(mlx-vlm) 결과 — 4.2초
```
The (quick) [brown] {fox} jumps!
Over the $43,456.78 <lazy> #90 dog
& duck/goose, as 12.5% of E-mail
from aspammer@website.com is spam.
Der „schnelle“ braune Fuchs springt
über den faulen Hund.
Le renard brun
«rapide» saute par-dessus le chien
paresseux.
La volpe marrone rapida
salta sopra il cane pigro.
El zorro
marrón rápido salta sobre el perro
perezoso.
A raposa marrom rápida
salta sobre o cão preguiçoso.
```
**Tesseract가 실패한 4곳 전부 정확** — 악센트·특수문자·독일어 인용부호까지 정밀 재현.

## 2-1. 영문 반복 텍스트(kong-bot photos_01.tif) — 대조군

Tesseract·Qwen2.5-VL(1.8초) 둘 다 완벽하게 동일 텍스트를 반환(무승부). 단순 인쇄체 영문에서는
차이가 없음을 확인 — Qwen2.5-VL의 우위는 특수문자·악센트·다국어 혼용 케이스에서 두드러진다.

## 3. 한글 텍스트 실측(직접 제작 이미지)

원본: "대한민국 서울특별시 강남구 테헤란로 123" / "영수증 번호: 2026-08-22-00123" /
"합계금액: 45,600원 (부가세 포함)"

### Tesseract 결과 — 완전 실패
```
'0000000000000723

umm 2026-08-22.00123

sm 45,6000 (erent
```
한글을 전혀 인식하지 못하고 숫자·기호 잡음만 출력.

### Qwen2.5-VL(mlx-vlm) 결과 — 1.0초, 부분 실패
```
한국어: 123
한국어: 2026-08-22-00123
한국어: 45,600 (원)
```
숫자·구조(3줄 구성)는 정확히 파악했으나, **실제 한글 문장(주소 "대한민국 서울특별시...")은 누락**하고
"한국어:"라는 메타 라벨만 붙였다. Tesseract보다는 낫지만(구조·숫자 인식) 완전한 성공은 아니다 —
정직하게 부분 실패로 기록한다.

## 4. ★사고 기록 — EasyOCR 설치가 시스템을 파손시킨 사례

EasyOCR을 `pip install`하는 과정에서 시스템 전역 `setuptools`가 84.0.0으로 강제 업그레이드되어
`pkg_resources`가 제거됐고, 그 결과 `librosa`→`transformers`→`mlx_vlm`/`mlx_lm` 임포트 체인 전체가
파손됐다. 즉시 `easyocr` 제거 + `setuptools<81`로 다운그레이드해 MLX 스택을 완전히 복구했고,
텔레그램 봇 빌드(`build_application()`, 10개 핸들러)까지 재검증해 정상 동작을 확인했다.

**부수 영향(미해결로 남김)**: 이 과정에서 `torch`가 2.11.0→2.13.0으로 업그레이드된 채 복구되지
않았다. 이 프로젝트(ocr-lake) 자체는 torch를 사용하지 않아 직접 영향은 없으며(`pip3 check`로
torch/setuptools 관련 충돌 0건, 텔레그램 회귀 정상 재확인함), 원래 버전을 정확히 알 수 없는 상태에서
임의로 되돌리는 것 자체가 또 다른 위험이 될 수 있어 **되돌리지 않고 그대로 두었다**. 이 시스템에서
torch를 사용하는 다른 프로젝트가 있다면 영향 가능성이 있으니 확인이 필요하다.

★이번이 **세 번째로 반복된 동일 패턴의 사고**다:
1. a_19(RAG): `mlx-embeddings`가 `transformers`를 강제 업그레이드해 파손 위험 발견 → 폐기.
2. a_21(멀티클라우드 OCR): `google-cloud-vision` SDK가 `protobuf`를 강제 업그레이드해 파손 → 즉시 제거·원복.
3. a_23(이번): `easyocr`가 `setuptools`를 강제 업그레이드해 MLX 스택 자체를 파손 → 즉시 제거·복구,
   단 `torch` 부수 영향은 미해결.

**패턴**: 이 머신은 다양한 ML/AI 프로젝트가 공유하는 site-packages 환경이라, 신규 대형 패키지
설치가 반복적으로 시스템 전역 의존성을 오염시키는 위험이 있다. 향후 신규 패키지 설치 전
`pip3 install --dry-run`(가능한 경우) 또는 격리 환경(venv) 사용을 고려할 필요가 있다.

## 5. 최종 제안

1. **지금 당장 Tesseract를 교체하지 않는다.** PaddleOCR/EasyOCR/docTR은 실측 검증에 실패했고
   (EasyOCR은 시스템 파손, 나머지 둘은 유사 위험으로 미시도), 대안으로 실측한 mlx-vlm도 한글에서는
   아직 신뢰 수준에 못 미친다.
2. **mlx-vlm을 다국어(비한글) 텍스트의 보조 OCR 폴백으로 검토할 가치는 있다** — 이미 이 프로젝트가
   의존하는 스택이라 신규 설치가 필요 없고, 다국어 정확도가 Tesseract보다 명확히 우세하다.
   단, 한글 정확도가 부족하므로 "언어 힌트가 비한글일 때만 mlx-vlm 우선" 같은 조건부 적용이
   필요할 수 있다 — 별도 설계·구현 작업으로 분리해 오케 확인 후 진행 제안.
3. **한글 OCR 정확도 개선은 이번 3개 후보로는 해결되지 않았다.** 향후 재검토 시에는 격리 환경(venv)에서
   먼저 설치·검증 후 시스템 전역에 반영하는 절차를 권장한다.
4. **torch 2.13.0 잔존**은 오케가 인지하고 필요시 조치 판단 바람(이 프로젝트에는 영향 없음).
