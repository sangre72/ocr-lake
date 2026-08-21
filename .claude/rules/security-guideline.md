# Security guideline — malicious-script/XSS prevention (MUST, user 2026-08-01)

> # ⭐ TOP principle (user 2026-08-01): security check = always highest priority
> **Security check + standard-compliance = this project's absolute top.** Ahead of any feature·schedule·convenience.
> XSS·injection·auth-bypass·secret-leak·malicious-file etc = **done condition** — not done without security check (sanitize·CSP·file-verify·auth) passing.
> New screen·input·file·API added → security check mandatory. All workers·all tasks, always on.

> **Prevent security-violating script use(보안위배 스크립트 방지).** User·admin input (posts·comments·editor·profile etc): block malicious script (`<script>`, `on*=`, `javascript:`, `data:` etc) from being planted·executed at root. Sensitive health-info → security = top axis w/ standard-compliance.

`~/git/sky` all tasks always on. With design/accessibility rules. Feature·permission symmetry: [feature-consistency-guideline.md](./feature-consistency-guideline.md).

## 1. XSS prevention (input→store→render whole path)
- **No direct HTML render(HTML 직접렌더 금지)**(`dangerouslySetInnerHTML`) — only after **sanitize**.
  - Rich editor (admin board etc) body HTML = **2-layer defense**:
    1. **On store(server)**: `sanitize-html` allowlist tags/attrs only. Strip `<script>`·`on*`·`style`·`javascript:`/`data:` URL·`<iframe>`(outside allowlist).
    2. **On render(defensive)**: re-sanitize w/ `isomorphic-dompurify` then show.
  - Allowed tags (editor output only): p,br,strong,em,u,s,h1~h4,ul,ol,li,blockquote,a,img,table/tr/th/td,code,pre.
  - `a[href]`=http/https/mailto only + rel="noopener noreferrer". `img[src]`=allowed domains(self/CDN/Azure) only, alt.
- **Plain-text input**(review·Q&A·comment etc, non-editor): no HTML render → React default escape safe. No `dangerouslySetInnerHTML`.
- Server(Server Action/Route Handler): **don't trust input(입력 신뢰 금지)** — zod validate + sanitize. Client validation alone not trusted.

## 2. CSP (Content-Security-Policy) hardening
- ✅ **nonce done(a_182, 2026-08-05)**: `src/proxy.ts`(Next 16 middleware→proxy rename) per-request nonce → inject CSP `script-src 'self' 'nonce-<n>' 'strict-dynamic'` + propagate `x-nonce`. Next auto-applies to framework scripts·`<Script>` on SSR. **Remove `unsafe-inline` from prod script-src**.
  - dev: report-only + keep `unsafe-inline`/`unsafe-eval` for turbopack HMR (not in deploy artifact).
  - `object-src 'none'`, `base-uri 'self'`, `frame-ancestors 'none'`(clickjacking), `form-action 'self'`, `connect-src` self+allowed origins.
  - ★nonce use → page dynamic rendering (static/CDN caching·PPR limit) tradeoff. ★proxy = nonce injection only, no auth decision(인가 판단 금지)(CVE-2025-29927).
  - style-src keeps `unsafe-inline`(Next/Tailwind many inline styles — block script XSS first). Follow-up: style nonce/hash hardening room.

## 3. File-upload security (attachment·editor image)
- Executable files (exe/js/html/svg etc script-capable) **block**. MIME·ext allowlist.
- Stored filename = **server random gen**(prevent path-traversal·overwrite), don't trust original filename.
- SVG upload = XSS vector → block or sanitize. Consider image re-encode.
- Internal(PRIVATE) files = serve via auth(§17), no direct exposure.

## 4. Etc
- **PII security policy(정본/canonical)**: PII grading·encryption·search/display·key-mgmt·collection policy follow [`docs/planning/standards/pii-protection-policy.md`](../../docs/planning/standards/pii-protection-policy.md)(canonical privacy policy).
- Auth: JWT httpOnly cookie, no middleware-only auth(CVE-2025-29927), DAL/server re-verify.
- ★Client fetch MUST go via **apiClient(`apiGet/apiPost/...`)**(no raw `fetch()`). Reason: must ride common 401 handling(login redirect + block data return) → 0 data leak on auth-fail. raw fetch doesn't filter 401 → stale data stays after session expiry(a_214). blob etc apiClient-unfit → judge 401 then call `redirectToLogin()` directly. SSR page/layout: requireRole/requireSession **before** data query (fail → redirect).
- Secrets: env/server-only, no NEXT_PUBLIC_* exposure, no commit.
- SQL: Prisma param binding (raw SQL → watch injection).
- Deps: periodic vulnerable-package check.

## Verify
- Editor/board: **XSS payload injection test**(`<script>`, `<img onerror>`, `javascript:` link) neutralized on store·render — Playwright/unit test.
- 0 non-sanitized HTML render paths.

Rationale: user "prevent security-violating script use". Editor research(sanitize-html 2-layer). Sensitive health-info service.
