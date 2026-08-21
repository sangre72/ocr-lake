# Data naming standard (based on MOIS 공통표준용어 — user 2026-08-01)

> All data fields **displayed/input on screen**: column names follow **MOIS(행안부) 공통표준용어/표준단어**, apply consistently to React vars·form `id`/`name`. All screen-displayed data = target.

## Principles
1. **논리명(Korean label) ↔ standard 물리명(EN abbrev) ↔ JS var/form id** = 3-tier mapping managed as standard dictionary.
   - MOIS standard 물리명 mostly UPPER_SNAKE (e.g. `USER_NM`, `RSVT_DE`).
   - **React var·form id/name = 물리명 → camelCase**(e.g. `USER_NM`→`userNm`, `RSVT_DE`→`rsvtDe`).
2. **Dictionary in `src/lib/`** as module (e.g. `src/lib/naming.ts` or `field-dictionary.ts`).
   - Columns: 한글라벨·표준약어·camelCase·domain(type)·설명. Screen labels·form fields reference this dict.
   - Rationale: `docs/planning/research_naming_standard.md`(MOIS standard-abbrev dict·mapping table).
3. **Form fields**: `<input name="userNm" id="userNm">` = standard camelCase. zod schema keys same.
4. **Data object keys**: mock·DTO·component props field names also unified standard camelCase (no dup·no arbitrary abbrev).
5. **Neologism not in standard**(job categories etc): combine nearest standard words; if none, register in dict as in-house standard extension then display.

## Application scope
- **All displayed data**(list columns·detail·form input·search/filter keys) apply.
- New screens(a_14 etc): standard from start. Existing: gradual migration(on refactor).
- DataView column defs, form schema, mock fields must use standard-dict keys.

## Verify
- Form id/name·React vars match standard-dict abbrev (review/lint). No arbitrary naming(e.g. `name1`, `email_addr`, `날짜`).

Rationale: MOIS 공통표준용어/공통표준단어 고시. Detailed dict: `docs/planning/research_naming_standard.md`.
User: "screen data column names follow MOIS standard, apply to react var·form id/name".
