# Design guideline (필수 준수 — user 2026-08-01)

> **All design = stylish, beautiful color.** No plain default mockup. **High-quality visual = part of pass bar.**

Applies: `~/git/sky` all UI work (web/ 및 이후).

## Tone & mood
- **신뢰·케어(bright·warm)** — 돌봄·요양 안심 온기. no cold gray-only, warm neutral + vivid accent.

## Requirements
1. **Beautiful palette**: brand color + semantic(success/warn/danger/info). no black-white+gray-border only.
2. **Design tokens**: color·typo·spacing·radius·shadow·motion tokenized(Tailwind theme/CSS vars) consistent.
3. **Typo hierarchy**: title/body/caption scale clear·readable font.
4. **Spacing·rhythm**: generous whitespace·aligned grid. no cramped.
5. **Component polish**: card·button·badge·table·tab = radius·shadow·hover·focus·transition. status badge = semantic color.
6. **Dark mode**(if possible): light/dark token pair.
7. **A11y**: contrast AA·focus ring·keyboard.
8. **Docs(/docs)**: no raw markdown dump. render as TOC+pages.

## Forbidden (anti-pattern)
- white bg+gray 1px border card list "mockup" level / raw markdown pipe-table·codefence exposed / no-color·no shadow/radius/hover plain elements.

---

## ★ UI robustness checklist (필수 준수 — user 2026-08-08 u_141/u_142)

> "박스 만들면 내용물 넘치면 안 되지, 레이아웃 2개 잡아야지." 2026-08-08 반복 UI 버그(dropdown 넘침·A4 mobile 잘림·본문 메뉴 중복·box content 넘침) → **불변 규칙** 재발 방지. all UI work(with design·a11y rules).

### 1. Box/container no-overflow (★최다 버그)
- **flex child = `min-w-0` 필수** — 없으면 child content(preview+long text)가 cell 밖 확장→넘침·잘림.
  (실사고: theme dropdown preset button `w-full min-w-0` 없어 content 393px > panel 359px.)
- **long text = `truncate`(1줄) or `break-words`(multi)** — name·desc·URL.
- container overflow 명시(`overflow-x-auto` scroll or `hidden`). **fixed-width = `max-w-*` + 화면 대응**.

### 2. Layout 2종 (desktop·mobile)
- **desktop = sidebar(`lg:`)**, **mobile = hamburger overlay drawer**(no push body).
- **no 주 nav dup in body**: mobile inline-sidebar `hidden lg:block`. 마이페이지 등 = content-only(주 메뉴 X, 상단/hamburger 일원화).

### 3. Header dropdown 공통 패턴 (theme·notif 등 헤더 우측)
- **mobile = `fixed` viewport 기준**(`right-4 top-14`), **desktop = `sm:absolute right-0 top-full`**.
- ★ancestor `backdrop-blur`/`transform`/`filter` = fixed containing-block 오염(fixed 기준이 viewport 아닌 그 ancestor) → 실측 확인(헤더 backdrop-blur 존재).
- width `w-[min(100vw-2rem,20rem)]`, **inner content `min-w-0`**(§1).

### 4. Responsive 필수 (375px 검증)
- **fixed-width(A4 210mm 등) = mobile [scale down](container query cqw) or [container 가로스크롤]** — 억지 `max-width:100%` = 표 label 잘림(실사고: A4 canvas). **body 가로스크롤 always 0**. all UI **375px 좌우 잘림 0**.

### 5. Verify 규율 (★오늘 교훈)
- 잘림 검증 = **[container rect + inner content maxRight] 둘 다** — panel 이 viewport 안이어도 child 넘칠 수 있음(실사고: panel rect 만 보고 단정 → content 393px 넘침 놓침).
- **375px E2E** 실 rect(`getBoundingClientRect`) 측정. "추측 말고 rect 실측"(user).

### 6. Input UI
- no `inputMode`/`type` misuse(email 겸용 필드에 `tel` 금지 등) — 성격 맞게.

### 7. No system-internal 노출
- poller status·heartbeat·queue count 등 = no 일반 화면. **ADMIN_SUPER gate or hidden**(audit·health endpoint 등 내부 경로만).

> With: [accessibility-guideline.md](./accessibility-guideline.md)·[code-structure.md](./code-structure.md). 요소별 상세 도감 = 후속(과투자 지양).

근거: user "관리자 목업 아름답게", "모든 디자인 스타일리시·아름다운 색". UI robustness: u_141/u_142(2026-08-08) — 반복 UI 버그(u_124~140: dropdown 넘침·A4 잘림·메뉴 중복·poller 노출) 불변 규칙화.
