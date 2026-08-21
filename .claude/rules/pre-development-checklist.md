# Dev start·done checklist (MUST — derived from 2026-08-01 full audit)

> After login·account·board impl, **7-perspective full audit** derived gate, applied to all future feature dev.
> Detailed findings: [`docs/planning/standards/audit-2026-08-01-findings.md`](../../docs/planning/standards/audit-2026-08-01-findings.md).
> Kept **together with** existing rules(security·naming·design·accessibility·modularization·feature-consistency) — this doc = their summary gate.

## ★ Absolute top-2 axes (done conditions)
1. **Security** — no done without below security items passing.
2. **MOIS(행안부) naming standard** — no done without new-column Deny risk 0, unregistered-word exception filed.

---

## A. Before start (design) — write first
- [ ] **Create field list** written, **Update = same list + attachment parity** designed (feature-consistency).
- [ ] **Permission×feature table**(GUEST/CLIENT/CAREGIVER/ADMIN × feature) draft.
- [ ] **New column** → MOIS standard-word mapping → if none, prep exception(TERM-EXC-00xx) → fix domain type/length.
- [ ] **mock if needed**: only in global `src/mocks/` or that feature's `app/<feature>/_mocks/`(page-having feature)·`features/<pure-module>/mocks/`(page-less module). **No direct mock import in component/lib**(inject via props/DAL).
- [ ] **Module placement**(code-structure §4): page-having feature = `app/<feature>/`(_lib·_components·_actions cohesion). Page-less pure logic only → `features/<module>/`(index.ts barrel). No circular-ref·server-only violation.

## B. During impl — Security (top)
- [ ] **Don't trust input(입력 신뢰 금지)**: server(Server Action/Route) zod validate + sanitize. Client validation alone not trusted.
- [ ] **XSS**: text = React escape(no HTML render). Editor HTML = sanitize 2-layer(store sanitize-html + render dompurify). `dangerouslySetInnerHTML` only after sanitize. **Don't block XSS via zod refine**(sanitize defends).
- [ ] **Authz**: UI hide ≠ authz. Server Action·REST·DAL mutation: `viewer` role·**ownership re-verify**(no redirect, return result). No middleware-only authz(CVE-2025-29927).
- [ ] **No response exposure**: don't put USER_NO·email·PASSWORD·TKN_ID(internal mapping) in response. Public identifier only.
- [ ] **File upload**: ext+MIME allowlist, block exec/script/SVG/HTML, stored filename server-random, PRIVATE auth-serving.
- [ ] **Secrets**: env·server-only. No signing w/ fallback constant(fail if prod unset). No `NEXT_PUBLIC_*`·no commit.
- [ ] **Rate-limit**: sensitive paths(login·pw-change·refresh). ※ current rateLimitStub = in-memory — **Redis required before multi-instance**.

## C. During impl — API/data
- [ ] Method standard: query GET · create POST · update PATCH · delete DELETE.
- [ ] envelope: success `{data,meta:{requestId}}` / error `{error:{code,message,details,requestId}}`. validation details = `{issues:[{path,message}]}` unified.
- [ ] Paging: page/size camelCase, size max 100. Bulk query = DB search(no memory filter). Sort `?sort=-regDt`.
- [ ] Error: try/catch, no stack·DAL-raw exposure, status judged by **structured error code**(no Korean regex).
- [ ] OpenAPI(openapi.ts) register — 0 miss on route add.
- [ ] DB: 4 audit-columns·NOT NULL·DEFAULT·CHECK·FK onDelete·index·**soft-delete DEL_YN + query WHERE DEL_YN='N'**·high-freq-update = VER optimistic lock(UPDATE WHERE VER=old). Polymorphic ref = orphan-cleanup plan.

## D. During impl — front/design/accessibility (public front = thorough)
- [ ] Design tokens only(no hardcoded color), verify both light/dark. Use next/image.
- [ ] Semantic markup·heading hierarchy·keyboard op·focus-visible·contrast AA.
- [ ] Form: label htmlFor + **aria-invalid + aria-describedby**(error), required = `*`+sr-only "(필수)".
- [ ] Image alt, icon aria-label/aria-hidden, toggle aria-pressed, toast/count aria-live.
- [ ] Status badge = color+text together. empty/skeleton/error state UI.
- [ ] DataView pattern(view-switch·search-filter-sort·paging·URL-sync) reuse.

## E. Before done — verify gate (no done without passing)
- [ ] **Parity one-line check**: every field·attachment made on create — **viewable·changeable in edit screen?** No → no done.
- [ ] **Security scenario**: self allow / other deny / ADMIN(per policy) / unauth 401. XSS payload neutralized.
- [ ] **Naming**: form id/name·zod key·DTO field = standard camelCase. New word exception filed. Meta-validation Deny 0.
- [ ] **tsc 0** + change-related Playwright(+ public front = axe violation 0). Related spec+core-regression instead of full e2e re-run(network saving).
- [ ] **E2E completeness**: API exists → front call exists? / UI shows real data? / data passed on tab-switch?
- [ ] **Permission×feature table** final left in result.

## F. Before deploy (P0 — else prod breaks/unlawful)
- [ ] `SERVER_BOOT_ID` fixed env injection(prevent all-logout·scale-out session-break per deploy).
- [ ] env zod boot-validation(process exit if AUTH_SECRET·DATABASE_URL unset).
- [ ] Healthcheck `/api/health`(liveness)·`/api/ready`(DB check) + graceful shutdown(SIGTERM→drain→$disconnect).
- [ ] Dockerfile(standalone·non-root) + Azure Blob real impl(prevent local-disk loss).
- [ ] DB migration automation(prisma migrate deploy or idempotent SQL runner), backup(PITR).
- [ ] **ACCESS_LOG access-audit**(sensitive health-info query record — 개인정보보호법 duty) load.
- [ ] CSP remove `unsafe-eval`→nonce→enforce, rateLimit Redis, custom 404/500, TZ=Asia/Seoul.

Rationale: user "as guide for future dev find·check issues, security·MOIS naming = top level". 2026-08-01 7-perspective full audit.
