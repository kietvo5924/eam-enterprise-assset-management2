---
title: 'Refactor Frontend Structure'
type: 'refactor'
created: '2026-05-29'
status: 'done'
baseline_commit: 'e628e9369e1fbc1172b925db3fff271c9fec67ba'
context: 
  - '_bmad-output/planning-artifacts/architecture.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The `SystemTenants.tsx` file is currently placed directly inside the `src/features/system-admin/` folder. This violates the architecture guideline which requires all feature-specific components to be placed inside a `components/` subfolder.

**Approach:** Move `SystemTenants.tsx` to `src/features/system-admin/components/SystemTenants.tsx` and update any imports that reference this component (likely in `App.tsx` or similar routing files).

## Boundaries & Constraints

**Always:** 
- Keep the internal code of `SystemTenants.tsx` untouched.
- Ensure the frontend builds successfully after the move.

**Ask First:** 
- If other files also need significant structural changes beyond fixing the import path for `SystemTenants.tsx`.

**Never:** 
- Delete or modify the logic within `SystemTenants.tsx`.
- Create placeholder `hooks/` or `components/` global folders unless requested; stick only to moving `SystemTenants.tsx`.

</frozen-after-approval>

## Code Map

- `web-portal/src/features/system-admin/SystemTenants.tsx` -- Source component file to be moved.
- `web-portal/src/features/system-admin/components/SystemTenants.tsx` -- Target destination for the component.
- `web-portal/src/App.tsx` -- Likely contains the routing import for SystemTenants that needs updating.

## Tasks & Acceptance

**Execution:**
- [x] `web-portal/src/features/system-admin/components/` -- Ensure the destination directory exists.
- [x] `web-portal/src/features/system-admin/SystemTenants.tsx` -- Move the file into the `components/` subfolder.
- [x] `web-portal/src/` (all files) -- Search and replace the import path pointing to `features/system-admin/SystemTenants` with `features/system-admin/components/SystemTenants`.

**Acceptance Criteria:**
- Given the frontend codebase, when the type check and build is run (`npm run build`), then it must succeed without any "module not found" errors related to `SystemTenants`.

## Verification

**Commands:**
- `cd web-portal && npm run build` -- expected: BUILD SUCCESS

## Suggested Review Order

**Component Migration**

- Updated import path for SystemTenants component.
  [`App.tsx:13`](../../web-portal/src/App.tsx#L13)
