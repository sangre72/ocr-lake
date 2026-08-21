# Web accessibility guideline (필수 준수 — user 2026-08-01 "접근성 시작부터")

> 돌봄·요양 플랫폼 주 사용자 = 고령자·장애인·저시력. a11y = build in from start, all UI (KWCAG 2.2 / WCAG 2.2 AA).

Applies: `~/git/sky` all UI work. With design-guideline.

## 적용 강도 차등
- **Public front(이용자 영역) = strict(AA full)**: 랜딩·가입·신청·검색·예약·FAQ·약관·이용자 포털. 12 reqs all strict + axe 0.
- **Admin(/admin/*) = baseline**: 시맨틱·키보드·라벨·명도대비 basics 지키되 front-level(axe 0·full keyboard E2E)까지는 불요(내부 전문 사용자·과투자 지양). 보호사/이용자 포털 = front 준함.

## 12 requirements
1. **Semantic markup**: header/nav/main/footer, heading order(h1→h6), list/table semantic tags.
2. **Keyboard-only**: all interaction(menu·button·form·accordion·tab·modal) Tab/Enter/Esc/arrow. modal focus-trap·logical tab order.
3. **Focus visible**: focus-visible ring(대비 충족). no `outline:none`-only.
4. **Contrast**: text AA(normal 4.5:1·large 3:1)·UI component 3:1. **all theme/dark preset AA**.
5. **Alt·label**: img `alt`·icon-button `aria-label`·form `<label for>`·decorative `aria-hidden`.
6. **ARIA proper**: native first, only where needed role/aria-*(expanded·current·live). no overuse.
7. **State**: not color-only(badge text/icon 병기). error = aria-invalid + message.
8. **Dynamic alert**: toast·live update `aria-live`(polite/assertive).
9. **Motion**: respect `prefers-reduced-motion`.
10. **Form a11y**: label·desc·error via aria-describedby·required mark·auth step screen-reader.
11. **Zoom/responsive**: 200% zoom no content loss·text reflow.
12. **Lang**: `<html lang="ko">`.

## Verify
- Playwright + **axe-core**(@axe-core/playwright) scan(serious 0). keyboard-only key flow(가입·예약·검색·메뉴) E2E. theme preset contrast.

근거: 장애인차별금지법(웹접근성 의무)·KWCAG 2.2·WCAG 2.2 AA. user "구체 개발 전에 접근성도 시작부터".
