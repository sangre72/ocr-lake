# Feature Consistency · Per-Role Feature Matrix (MUST)

> Always applies as dev base guideline. With security(`.claude/rules/security-guideline.md`)·standard(행안부 naming) = **done condition**.
> Detail table·domain matrix: [`docs/planning/standards/feature-consistency.md`](../../docs/planning/standards/feature-consistency.md)

Applies to all feature work in `~/git/sky`(screen·Server Action·REST·DAL).

---

## 1. What feature consistency means

**All paths·roles handling the same business(entity) provide the same feature set symmetrically.**

| Symmetry axis | Meaning | Violation example |
|---------|------|---------|
| **CRUD symmetry** | Create's input·attachment also viewable·changeable in Update | attachment in create only, none in update |
| **Path symmetry** | screen Server Action & REST(`/api/v1`) same authz·same fields | REST only Bearer, screen update has authz hole |
| **Role symmetry** | roles differ only in *allowed scope*, *feature menu structure* consistent | admin update form alone lacks attachment |
| **Representation symmetry** | list·detail·update same DTO fields·naming | detail has attachment, update lists 0 |

**Forbidden**: remove whole feature block via `mode === 'edit'`. **Allowed**: edit differs only in *initial-value injection*·*delete UI*·*cap slot*.

---

## 2. Required rules (implementation)

### 2-1. Create ↔ Update parity
1. Write the create-form field list first (title·body·rating·secret·attachment·pin etc.).
2. Update form = **same list** base. Initial values = existing resource.
3. Attachment·related resource: update screen = **show existing list + delete + add(within cap)**; server = re-verify ownership/ADMIN then soft-delete·upload.
4. Shared component(`BoardWriteForm` etc.) → create/edit **one contract** — branch only on data·slots.

### 2-2. One-line check before done (required)
> **Can every field·attachment·related data made at create be viewed·changed on the update screen?** No → **no done**.

### 2-3. Authz consistency

| Layer | Rule |
|------|------|
| UI | button hide = UX. **not authz** |
| page/layout | `requireSession` / `requireRole` may redirect |
| Server Action · REST · **DAL mutation** | check role·ownership via `viewer` arg. **no redirect**(fail via JSON/result object) |
| middleware/proxy | optimistic cookie-existence check only (CVE-2025-29927) |

Don't put `await requireRole()` in DAL. Caller(action/API) injects session, DAL judges via `viewer.role`/`canManage*`.

### 2-4. Path consistency (screen · REST)
- Same business: same DAL·same authz fn·same field DTO(same PII masking).
- Adding REST → no "screen-only work / API-only work". If no capacity, leave **unimplemented-symmetry list** in instruction Notes.

### 2-5. Verification scenario (≥1 applicable item before done)
- **Parity**: create(incl. attachment) → confirm list on update → delete 1·add 1 → reflected in detail.
- **Authz**: self allow / other deny / ADMIN allow(if per policy).
- **Unauthenticated**: 401 or login redirect(per path convention).

---

## 3. Per-role feature matrix (required output when working)

Leave a **role × feature** table in new/extended feature instruction or PR/ar result.

### 3-1. Table template (copy & fill)
```markdown
### 권한별 기능 일람 — <도메인명>

| 기능 ID | 기능 | GUEST | CLIENT | CAREGIVER | ADMIN | 비고(소유권·등급) |
|---------|------|:-----:|:------:|:---------:|:-----:|-------------------|
| X-LIST  | 목록 조회 | △ | ✓ | ✓ | ✓ | … |
| X-READ  | 상세 | △ | ✓ | ✓ | ✓ | 비밀글: 작성자+ADMIN |
| X-CREATE| 작성 | ✗ | ✓ | △ | ✓ | NOTICE=ADMIN only |
| X-UPDATE| 수정 | ✗ | 본인 | 본인 | ✓ | 첨부 포함 |
| X-DELETE| 삭제(소프트) | ✗ | 본인 | 본인 | ✓ | DEL_YN |
| X-ATTACH| 첨부 추가/삭제 | ✗ | 본인 | 본인 | ✓ | Create와 동일 상한 |
```
- ✓=allow, ✗=deny, △=conditional/partial, 본인=ownership required.
- **ADMIN** = ✓ if policy allows managing all resources. Branch scope(`ADMIN_BRANCH`) noted in 비고.
- UI hide & server deny must be **same result**(no button + server 403/error).

### 3-2. Role codes (fixed)

| role | 포털 | 비고 |
|------|------|------|
| `ADMIN` | `/admin` | grade: ADMIN_SUPER / ADMIN_OPS / ADMIN_BRANCH |
| `CAREGIVER` | `/caregiver` | grade: CG_* |
| `CLIENT` | `/client` | grade: CL_* |
| (비로그인) | 공개 라우트 | GUEST — 목록·공지 읽기 등 |

Detail grades → part1·this doc's standard domain table. On implement, grade branching **only what's explicitly in the table**.

### 3-3. Feature ID naming
`{도메인약어}-{동사}` — e.g. `BBS-CREATE`, `BBS-ATTACH-DEL`, `RSV-ACCEPT`, `ADM-BOARD-PIN`.

---

## 4. Checklist for instruction·done docs

Before start:
- [ ] Write create field list
- [ ] Confirm Update = same list + attachment parity
- [ ] Per-role feature matrix draft
- [ ] State ownership rule(`canManage*` / self / ADMIN)

Before done:
- [ ] One-line parity check passed
- [ ] Double: UI hide + server re-verify
- [ ] self/other/ADMIN(if applicable) scenario
- [ ] PII·USER_NO not exposed in response (security guideline)
- [ ] Final per-role feature matrix in ar/PR

---

## 5. Anti-patterns (real incidents)

| Anti-pattern | Result | Do instead |
|----------|------|------------|
| `{!isEdit && <FileUpload />}` | update attachment hole | list+add+delete in edit too |
| implement only "CRUD security" from instruction | text-only update, attachment missing | field parity table required |
| DAL `requireRole` redirect | Bearer API returns HTML login | viewer check + return result |
| button-only hide | direct URL·API bypass | server re-verify |
| duplicate form per role | admin-only feature missing | one form + role props |

---

## 6. Related docs
- Standard detail·domain matrix: `docs/planning/standards/feature-consistency.md`
- API·RBAC: `docs/planning/standards/api-protocol.md`
- Roles·IA: `docs/planning/part1_ia_roles_data.md`
- Security: `.claude/rules/security-guideline.md`
- Module structure: `.claude/rules/code-structure.md`

Basis: user "make feature-dev consistency·per-role feature matrix a dev base guideline".
