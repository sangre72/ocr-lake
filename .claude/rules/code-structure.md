# Code Structure Rules (MUST — user 2026-08-01)

Always applies to all code work in `~/git/sky/web`.

> **Also required**: feature consistency · per-role feature matrix → [feature-consistency-guideline.md](./feature-consistency-guideline.md)
> Standard detail table → `docs/planning/standards/feature-consistency.md`


## 1. Isolate mock data in a separate dir (user: "later just delete the dir")

> Goal: **when removing mocks / swapping to real API, deleting `src/mocks/` alone suffices.**

- **All fake data · fake stores · mock auth codes** → isolate under `src/mocks/` as per-domain files. e.g. `src/mocks/{workers,reservations,settlements,clients,theme,auth,notifications,public}.ts`, `src/mocks/index.ts`.
- **Real logic never imports mocks directly.** DAL(`src/dal/*`)·server actions·components don't scatter-reference mocks — inject only at a **single boundary** (e.g. `src/dal/data.ts` references only `src/mocks/`, or `src/mocks/index.ts` barrel).
- No inline hardcoded mock arrays in components/pages → move to `src/mocks/`.
- Real backend: delete `src/mocks/` + swap only data boundary(DAL) to real fetch. Rest of code unchanged.
- Each mock file top comment: `// MOCK — 실서버 연동 시 제거`.

## 2. Libraryize (extract reusable common)

- Reusable **pure logic** (fee calc·contrast·date·format·status-map·theme tokens etc.) → `src/lib/` side-effect-free module.
- No hardcoded domain logic in components — call lib fn.
- Common UI primitives → `src/components/ui/`(shadcn). Domain components → `src/components/<domain>/`.
- Types shared via `src/lib/domain.ts`(or types). No duplicate defs.

## 3. Data-screen common standard (user 2026-08-01)

All data screens (list·search·history·admin) provide via reusable `DataView` pattern:
- **View toggle**: table ↔ gallery (card grid).
- **Paging**: pagination/load-more + page size(10/20/50) + total count.
- **Basics**: search·filter(per-domain)·sort·count summary·empty/skeleton/error·(if applicable) bulk-select·export·refresh.
- **URL sync**: filter·sort·page in querystring.
- **A11y**: semantic table/list, aria-sort, keyboard (front strict·admin basic).
- Don't reimplement per screen → **libraryize as common component**(src/components/ui or data-view).
- Basis: docs/planning/part1_ia_roles_data.md §2.4.

## 3-1. File line-count cap (user 2026-08-03 "files too long" · 2026-08-05 u_146 "modularize → right line count")

> **Too-long file hurts maintenance·modularity·review·portability.** Line count = mgmt metric.

> ### ★ Goal = "modularize to reach right line count" (user 2026-08-05 u_146)
> **Line count = outcome metric, modularization = means.** Don't force-cut/paste; **split modules by responsibility·domain boundary → each file lands at right count (rec ~300, cap 800).**
> - Not "over 800 → cut anywhere" but **"how many responsibilities does this file hold → split per-responsibility via §4 modularization·§2 libraryization"** → line count naturally right.
> - Split = **behavior-preserving pure refactor**. Barrel(`index.ts`) keeps public API so **external import paths don't break**(if must change → update all + regression test).
>
> ### ★★ Consider line count from the start (user 2026-08-05 — "doing it later means re-running all tests")
> **New files·features designed·built under 400 lines from the start.** Post-hoc split = re-run all regression → expensive.
> - Before start(§A checklist): "how many responsibilities → if likely >400, split files/modules from the start".
> - Goal: each file **under 400**(ideal ~200, rec ~300). If trending over → split per-responsibility right there(no bulk split later).
> - Components → sub-components·hooks·pure fns; DAL → per-responsibility files; specs(openapi etc.) → per-domain files, **from the start**.
> - Why: post-completion split needs tsc + full E2E/regression re-verify(cost·time). Split at dev time → only that feature's tests.

### Recommended thresholds (differentiated by nature)
| Range | Verdict | Action |
|------|------|------|
| **~200 lines** | ideal | — |
| **~300 lines** | rec cap | keep |
| **300~500 lines** | caution | check cohesion, split if growing |
| **500~800 lines** | warning | **plan a split**(domain·responsibility unit) |
| **>800 lines** | ★violation | **split required**(sign of many domains/responsibilities in one file) |

### Exceptions by nature (cap relaxed)
- **Spec/definition files**(openapi spec·type dict·codes·naming dict·route registration): data listings can be long → >800 allowed but **per-domain file split** recommended(e.g. openapi/ per-domain).
- **Generated artifacts**(prisma client etc.): out of scope.
- Else **logic/component/DAL files = strict cap**.

### Split method
- **Central DAL holding many domains** → extract per §4 placement: page-owning feature → `app/<feature>/_lib/`, page-less pure engine → `features/<module>/`. (e.g. data-db.ts 1900 lines → reservation·settlement·review to each app feature _lib, only pure reusable engine to features.)
- **Big component** → split sub-components·hooks·pure fns(lib).
- **A fn over 100 lines** → split into helpers.

### ★ Split-target registry (category·description·plan — user 2026-08-05)

> Violation/warning files' **list·category·split plan·progress = single-managed in one ledger**(inline in body goes stale) → **[docs/planning/standards/file-split-registry.md](../../docs/planning/standards/file-split-registry.md)**.

- Categorize nature → **apply different split method**: `LOGIC`(logic/lib)·`COMPONENT`(.tsx)·`DAL`(data*.ts) = strict cap / `SPEC`(openapi·codes·naming dict·route reg)·`TYPES`(domain.ts) = relaxed(>800 allowed, per-domain split recommended) / `GENERATED`(prisma) = out of scope.
- **New/modified file >800** → add registry row(file·lines·category·**description**·verdict·priority·split plan). If can't split now, at least priority(P).
  - **Description** column(what responsibility) required — basis for which boundary to split(user 2026-08-05: "need file with category and description").
- **On split start/progress** → verdict → 🔀 in-progress, note how far(1st helper extraction etc.) in plan column.
- **On split done** → verdict → ✅ + result·final line count. Regression spec pass required.
- **Procedure**: ① find >800 → register(category·description·plan) → ② at refactor split per that plan via §4/§2 → ③ tsc0 + regression pass → ④ update registry ✅.

### Verification
- At review/done, new/modified file **>800 → register + split plan**.
- Actual split work delegated per-domain via instructions, **P1(violation) first** — not all at once, per-domain unit with regression tests.

Basis: user "files too long, put recommended line count in standard" / "add split-target split work + need file with category·description"(2026-08-05). Central DAL bloat → resolved via §4 placement(app cohesion/pure-module separation).

## 4. Module placement — app cohesion is default, features = pure modules only (★user 2026-08-07 redefine)

> ### ★★ Grand principle (user 2026-08-07 — overturns prior "features first")
> **"Only pure logic that's perfectly separable → `features/`. A total (screen+logic+components collected feature) → `app/`."**
>
> - **`app/` is default.** Page(route)-owning feature → **cohere screen·logic·components·DAL·types in `app/<feature>/`**. No scatter forcing you across app·features two places — **co-location(related code beside screen).**
> - **`features/` = "page-less, pure-logic perfectly-separable module" only** (e.g. `attachment`·`finance` — not tied to a screen, reused everywhere, independent engine). Only those where portability(dir copy) truly matters.
> - Discriminator question: **"does this module have its own page(app route)?"** — yes → **integrate into app/<feature>/**(cohere _lib·_components·_actions beside) / no & pure logic·reusable engine → **keep features/<module>/**.
>
> ### ★ Portable-module exception — components cohere inside it too (user 2026-08-07 "copy attachment wholesale to use")
> **Self-contained module meant to be "copied dir-wholesale into another project as-is"** → even if it has components(tsx), **don't extract out, keep inside module**. Over "has components → app", **"will this module be copied wholesale?" takes precedence** — if yes, cohere components too in features(complete in one copy).
> - e.g. `features/attachment/`(incl. file-upload.tsx) — board·profile·certificate·signup reuse via `@/features/attachment` but keep wholesale-portable.

### app internal standard layout (page-owning feature)
```
app/<기능>/                     라우트(폴더=URL) + 그 기능 전부 응집
  ├─ page.tsx, <서브>/page.tsx  화면(주소)
  ├─ _lib/                      그 기능 순수 로직·DAL(server-only)·타입·매퍼
  ├─ _components/               그 기능 전용 컴포넌트
  ├─ _actions/                  서버액션
  └─ _mocks/                    그 기능 mock (// MOCK 주석, 삭제 가능)
```
- `_` prefix folders excluded from Next.js routing(private folder) → no URL. Screen·logic under one roof + no routing pollution.
- Portal-dependent feature → same layout under `app/<portal>/<기능>/`(admin/caregiver/client).

### features internal standard layout (page-less pure module only)
```
features/<모듈>/                자기 페이지 없는 재사용 엔진(이식 대상)
  ├─ lib/ · data.ts · index.ts  순수 로직·DAL·공개 배럴
  └─ (components/ 는 최소 — 화면 종속이면 app 으로)
```
- **Declare external deps**: index.ts top comment lists project-common deps(session·naming·ui·theme tokens) as "external deps".
- **Single boundary**: external → only index.ts public API. No circular ref, keep server-only boundary.

### Migration (existing features → app integration)
- Features split across app+features(board·settlement·membership·financial·caregiver·resume etc.) = **page-owning → app integration** targets. **Delegate sequentially per-domain**(behavior-preserving pure move + import path update + tsc0 + regression). Not all at once, per-domain with regression tests(same discipline as §3-1 registry).
- Page-less pure modules(attachment·finance) stay in features.

## 5. Current structure (target — app cohesion)
```
src/app/<기능|portal/기능>/    ★기능 전부 응집: page + _lib·_components·_actions·_mocks
src/components/ui/             공통 UI 프리미티브(shadcn) — 도메인 무관 재사용만
src/features/<순수모듈>/        ★페이지 없는 순수 로직 모듈만(attachment·finance…)
src/lib/                       전역 순수 로직·타입·유틸(도메인 횡단 재사용)
src/dal/                       전역 데이터 경계(RBAC·서버전용) — 남는 공통만
src/mocks/                     전역 mock(삭제 가능) — 기능전용 mock 은 app/<기능>/_mocks
```

Basis: user 2026-08-07 "if app is default, group features/modules by app. Only page-less whole modules → features". "Pure logic perfectly separable → features, a total collection → app". (Redefines 2026-08-01 features-first.)

## 6. Compare roles as arrays (user 2026-08-03 — "may have duplicate roles")

> **All role/permission comparison = array-includes(`['ADMIN'].includes(role)`), not direct string(`role === 'ADMIN'`).** A user may hold duplicate roles, and multi allowed-roles is common.

- Menu/button/screen gate: `roles?: string[]` + `roles.includes(viewer.role)`.
- DAL/server authz: `requireRole(['ADMIN','ADMIN_OPS'])` array. Single also `['X']`.
- New = array from start. Existing `role === 'X'` → migrate to array at refactor.

Basis: user "all role comparison as array. Duplicate roles may exist."

## 7. Common functions — catalog first (user 2026-08-03)

> **Before writing new logic, check [common function catalog](../../docs/planning/standards/common-function-catalog.md).** Exists → import & use it(no re-implement·no direct `role === 'X'`). Missing → make in lib/features & **add 1 line to catalog**.
> Background: rbac.hasRole exists yet 152 places compared directly → standard collapse. Catalog forces reuse instead of grep every time.

- Check catalog before start. Role→rbac, fee→settlement, session→session, active-job→activation, naming→naming, code value→codes.
- ★Role comparison via rbac fn(hasRole etc.) — no direct `role === 'X'`(with §6 array compare).
- New common fn = register in catalog. Same logic 2nd time = promote to lib + register. No re-invention.
- On finding direct compare·inline logic → migrate to catalog fn(at refactor).

Basis: user "make a common function list doc, use if exists·make & add doc if not."

## 8. Request-context standard — tenant·region·language (user 2026-08-03)

> **Prep future expansion(multi-tenant·multi-region·i18n).** Don't fully implement now; new code = **context-propagatable structure**. Detail: [request-context-standard.md](../../docs/planning/standards/request-context-standard.md).

- **Tenant**(per host/server): session has tnntId·brnchNo reserved. DAL query via `tenantWhere(ctx)` habit(now no-op). No hardcoded 'DEFAULT'/tenant.
- **Region**: care region via REGION lib. Multi-region = infra.
- **Language**(i18n): now ko-KR fixed but date·currency·sort via lib(date·format·localeCompare) as locale injection points. New bulk UI copy = constants for future i18n. Avoid direct `toLocale*('ko-KR')` hardcode.
- On activation(MULTI_TENANT_ENABLED·i18n), routing via these already makes filling values work.

Basis: user "tenant·server(region)·language(i18n) standard into guideline". Standardize atop existing tenantWhere.
