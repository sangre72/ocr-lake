# ocr-lake

텔레그램 봇으로 이미지·PDF·동영상을 받아 OCR 텍스트를 추출하고, 웹 화면(FastAPI + Next.js)에서 처리 이력을 조회하는 프로젝트입니다.

## 구성

- `core/`: 채널 무관 핵심 로직 — 이미지 유형 분류, OCR(Tesseract), PDF/동영상 처리, 저장소(SQLite), 분기 파이프라인
- `telegram_bot/`: 텔레그램 채널 어댑터(봇 엔트리·핸들러) + 오케스트레이터 운영 인프라
- `web/backend/`: FastAPI(업로드/이력 조회 API)
- `web/frontend/`: Next.js(업로드 화면·이력 목록)

## License

This project is distributed under the [PolyForm Noncommercial License 1.0.0](./LICENSE).

- **Personal / noncommercial use** (research, learning, hobby projects, nonprofits, educational institutions, etc.): free to use, modify, and distribute.
- **Commercial use** (companies, etc.): requires a separate commercial license agreement. Contact the repository maintainer to inquire.
