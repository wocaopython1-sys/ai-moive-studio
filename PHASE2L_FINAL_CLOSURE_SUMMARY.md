# Phase 2L Final Closure Summary

## 1. Scope

This final closure summary covers the Phase 2L functional scope completed on the `phase2k-workflow-display-guards` branch.

Included scope:

- Works Library media preview/download.
- Canvas archive success path.
- Canvas duplicate archive error-state.
- Runtime deployment evidence.
- DOM, Network, and DB validation evidence recorded by phase summaries.

Explicitly not included:

- stream/range implementation.
- video seek/range validation.
- media.py object_key route for Works.
- Provider, official API, generation, or compose changes.

## 2. Final Baseline

- final HEAD before this summary: 46321dae195a5178455a590d930bff5c0c8e3370
- branch: phase2k-workflow-display-guards
- remote: git@github.com:wocaopython1-sys/ai-moive-studio.git
- pushed state: origin/phase2k-workflow-display-guards reached 46321dae195a5178455a590d930bff5c0c8e3370 before this final summary.

## 3. E5 Works Media Result

Works preview/download backend endpoints completed:

- `/api/v1/works/{work_id}/items/{item_id}/preview`
- `/api/v1/works/{work_id}/items/{item_id}/download`

Frontend and permission validation completed:

- Frontend `/works` detail drawer preview/download completed.
- Owner access worked.
- Anonymous access returned `401`.
- Non-owner access returned `404`.
- Wrong item returned `404`.
- object_key query was ignored.
- object_key UI was masked/truncated.
- No media.py object_key route was used as Works permission basis.

## 4. E2 Canvas Archive Success Path Result

- Canvas archive click success path closed.
- target Canvas: 60aaebb2-1eed-44e7-b718-e6015b2d4c2d
- successful item: bbdd4c41-dfbf-4de7-96df-e80cdbe81985
- POST `/api/v1/works/from-canvas-final` returned `201`.
- created work: c85fc544-0f9c-455a-a82d-0cb6752dbd89
- created work_item: 741853b8-aff0-400c-a8e9-ff8f27a7fe9d
- `/works` displayed the created work.
- Created work was soft deleted after smoke validation.
- active_for_item returned to `0`.
- No password, token, cookie, or object_key value was output.

## 5. E2 Duplicate Archive Error-State Result

- Duplicate archive error-state closed.
- Frontend duplicate path fix committed: 0dfbda4 phase2l: fix duplicate canvas archive request path
- Frontend runtime rebuilt/recreated: sha256:a7979c3a6775ad3e17e28f1e044638bf82a0664514afa3ea0e0ef571d6d0d61d
- Duplicate click reached POST `/api/v1/works/from-canvas-final`.
- Backend returned `400`.
- Business message: 该 Canvas final 已归档为作品
- UI displayed the business error.
- active count remained `0`.
- No new active work was created.
- No cleanup was needed.

## 6. Important /api/v1/media Clarification

- Canvas page media preview may issue /api/v1/media requests.
- The duplicate archive validation must not be reported as no /api/v1/media appeared.
- The duplicate archive validation path was /api/v1/works/from-canvas-final.
- The Works permission basis remains the Works-scoped route, not media.py object_key route.
- object_key was not output.

## 7. Not Included / Still Pending Outside Phase 2L Closure

- stream/range is not implemented.
- video seek/range is not validated.
- media.py object_key route remains forbidden for Works.
- No Provider, official API, generation, or compose changes were made.
- No DB schema changes were made.

## 8. Repository / Deployment State

- Pushed through duplicate archive validation summary commit: 46321dae195a5178455a590d930bff5c0c8e3370
- This final closure summary is local until committed and pushed separately.
- Runtime `/` returned `200` during this final summary precheck.
- Runtime `/works` returned `200` during this final summary precheck.
- frontend: running and healthy.
- backend: running and healthy.
- postgres: running and healthy.
- redis: running and healthy.
- minio: running and healthy.
- celery-worker: running.
- celery-beat: running.
- Only `.env.demo` and `PHASE0_BASIC_AUTH.txt` remain untracked and must not be committed.

## 9. Final Judgment

- Phase 2L functional scope covered by this branch is closed.
- E5 Works media preview/download is closed.
- E2 Canvas archive success path is closed.
- E2 duplicate archive error-state is closed.
- No known E2 functional pending remains.
- stream/range remains a separate future phase.
- media.py object_key route remains forbidden for Works.
- Push of this final summary requires explicit user authorization.
