# Network budget rules (필수 준수 — user 2026-08-01)

> Network only when needed. 배경: Playwright browser·npm 반복 재설치로 5GB+ 소모.

Applies: `~/git/sky` all work (esp. worker).

## Forbidden
1. **No Playwright browser reinstall** (`npx playwright install`/`install-deps`) — already installed(local cache). verify = `npx playwright test` only.
2. **No repeated npm install** — `node_modules` exists. package.json unchanged → no `npm install`/`ci`. New pkg needed → **that pkg only** (`npm i <pkg>`), no full reinstall.
3. **No unneeded WebSearch/WebFetch** — internal impl 불필요. research-marked task only.
4. **No remote large assets** (font·image·model) — local/inline/system first (no external CDN, design-guideline 일치).

## Allowed
- WebSearch/WebFetch on explicit research task. package.json real new dep → install once. First-time env setup (skip if done).

## Verify lightweight
- No full e2e rerun → **changed-related specs + core regression only** (keep build/tsc). Playwright reuse local browser.

근거: user "네트워크 5기가 뭐하느라 → 꼭 필요한 경우만". 주범 = per-worker Playwright·npm 반복 다운로드.
