# Phase 2L-E2 Duplicate Archive Validation Summary

## 1. Scope

This summary records the Phase 2L-E2 duplicate archive error-state validation after the DUP-B2 frontend fix.

The validation target was the Canvas final archive button path. The expected behavior was that a repeated archive click reaches backend duplicate-check logic and displays the business error in the frontend.

Out of scope for this run:

- stream/range implementation.
- Provider, official API, generation, or compose calls.
- media.py object_key route as a Works permission basis.
- git push.

## 2. Baseline

- baseline HEAD: 0dfbda4d53f24ac172da61985a457730c6ffdc93
- branch: phase2k-workflow-display-guards
- remote: git@github.com:wocaopython1-sys/ai-moive-studio.git
- frontend runtime image: sha256:a7979c3a6775ad3e17e28f1e044638bf82a0664514afa3ea0e0ef571d6d0d61d
- target Canvas: 60aaebb2-1eed-44e7-b718-e6015b2d4c2d
- target item: bbdd4c41-dfbf-4de7-96df-e80cdbe81985
- node title: Phase2J fill_missing final compose
- baseline deleted work: c85fc544-0f9c-455a-a82d-0cb6752dbd89
- baseline active count: 0
- owner login was available in the browser.
- password, token, and cookie values were not output.

## 3. Network / Backend Result

- POST /api/v1/works/from-canvas-final appeared during the duplicate archive click.
- Backend log showed: POST /api/v1/works/from-canvas-final - 400
- HTTP status: 400
- Business message: 该 Canvas final 已归档为作品
- The request reached business duplicate-check logic instead of returning 401, which confirms the logged-in request path reached backend authorization and business validation.
- The frontend displayed the same business error: 该 Canvas final 已归档为作品
- The archive button recovered after the failed duplicate archive attempt: disabled=false.

## 4. DB Result

- active count after duplicate attempt: 0
- No active work was created by the duplicate archive attempt.
- No cleanup was required for new work records.
- The historical soft-deleted work remained present.
- Confirmed soft-deleted work id: c85fc544-0f9c-455a-a82d-0cb6752dbd89
- MinIO was not written or deleted.
- object_key was not output.

## 5. Important /api/v1/media Clarification

- Canvas page media preview may issue /api/v1/media requests.
- This run must not be reported as no /api/v1/media appeared.
- The duplicate archive validation path was /api/v1/works/from-canvas-final.
- The duplicate archive error-state did not rely on /api/v1/media.
- media.py object_key route was not used as the Works permission basis.
- object_key was not output.

## 6. Forbidden / Not Observed

- No Provider request was observed.
- No official API request was observed.
- No generation request was observed.
- No compose request was observed.
- No MinIO write or delete occurred.
- No password, token, cookie, object_key value, or secret was output.
- No frontend or backend code was changed in this run.
- No DB write was performed in this run.
- No build, restart, reload, or docker compose up/down was performed in this run.

## 7. Final Judgment

- Duplicate archive error-state is closed.
- Frontend fix successfully allowed the duplicate archive request to reach backend duplicate check.
- Backend duplicate check returned the expected business error.
- UI displayed the expected business error.
- No active work was created.
- E2 Canvas archive success path and duplicate error-state are now both closed.
- stream/range remains not implemented.
- media.py object_key route remains forbidden for Works.
- this run was not pushed.

## 8. Recommended Next Step
