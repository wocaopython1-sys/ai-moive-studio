# Phase 2L-E3 Works Media Route Runtime Summary

## 1. Scope

This phase completed the backend minimum implementation, runtime deployment, and route-level smoke validation for works-scoped media preview/download endpoints.

Included in this phase:

- works-scoped media preview endpoint.
- works-scoped media download endpoint.
- backend image build and backend/celery runtime recreate.
- route-level anonymous auth smoke.

Explicitly not included in this phase:

- owner preview/download 200 media validation.
- frontend `/works` preview/download integration.
- stream/range support.
- E2 Canvas archive click success-path follow-up.

## 2. Code Baseline

- code commit: `0ccf1905fb4f6dc306ef2f48ea83191475f4f26a`
- message: `phase2l: add works scoped media endpoints`
- modified files:
  - `backend/src/api/v1/works.py`
  - `backend/src/services/work.py`
  - `backend/tests/integration/test_works_api.py`
  - `backend/tests/unit/test_works_service.py`

## 3. Implementation Summary

- Added `GET /api/v1/works/{work_id}/items/{item_id}/preview`.
- Added `GET /api/v1/works/{work_id}/items/{item_id}/download`.
- Added `WorkService.get_work_item_media`.
- Both endpoints depend on `get_current_user_required`.
- The endpoints do not accept `object_key` from path, query, or body.
- `object_key` is read only from `WorkItem.object_key`.
- Access checks cover `Work.user_id`, `Work.deleted_at`, `WorkItem.work_id`, and `WorkItem.user_id`.
- Non-owner, deleted work, wrong work item, or missing media returns 404 or the existing project error style.
- Storage access is read-only through `get_object`.
- MinIO write was not added.
- MinIO delete was not added.
- Stream/range support was not implemented.

## 4. Test Summary

- unit pytest: `14 passed`
- integration pytest: `17 passed`
- py_compile: passed
- git diff --check: passed
- Warnings observed during tests are existing Pydantic, SQLAlchemy, FastAPI, datetime deprecation, or relationship warnings. They were not handled in this phase.

## 5. Runtime Deployment

- backend image: `sha256:c87752b01639f8c403a0fc130872562ffadcbf3b2f89663d3c26b913fa96dcba`
- rollback tag: `aicon-demo-backend:rollback-before-works-media-0ccf190`
- recreated services:
  - `backend`
  - `celery-worker`
  - `celery-beat`
- services not recreated:
  - `frontend`
  - `postgres`
  - `redis`
  - `minio`
- The backend compose startup command executed `alembic upgrade head` as an authorized no-op startup check.
- DB revision remains `030`.

## 6. Runtime Route Smoke

- backend `/health/`: `200`
- anonymous preview: `401`
- anonymous download: `401`
- deployment before baseline was `404` for preview.
- deployment after result is `401` for preview/download.
- conclusion: route exists and the auth gate is active.
- This does not prove owner 200 media access.

## 7. Logs / Side Effects

- No Provider or official API calls were observed.
- No generation or compose calls were observed.
- No MinIO put/remove/delete was observed.
- Anonymous 401 smoke may appear as an ERROR in backend logs. This was a test-induced auth failure, not a route failure.
- No rollback was executed.

## 8. Not Completed

- owner preview/download 200 not validated.
- owner/work/storage object sample not prepared.
- frontend `/works` not connected to preview/download.
- stream/range not implemented.
- E2 Canvas archive click success path still pending due to missing owner credentials.
- no push / not pushed.

## 9. Security / Boundary Notes

- `media.py` object_key routes are still not safe for `/works`.
- Frontend must not use `/api/v1/media/preview|download|stream/{object_key}` for works media.
- Works media URLs must be scoped by `work_id` and `item_id`.
- Provider, official API, generation, and compose remain out of scope.
- MinIO write remains out of scope unless separately authorized for a smoke sample.

## 10. Recommended Next Step

- If complete backend media validation is required, first perform owner/storage sample preparation read-only planning.
- Owner 200 validation likely needs owner credentials, a work, a work item, and a real storage object.
- If creating a smoke sample requires MinIO write, that write must be separately authorized.
- Do not connect frontend preview/download until owner route 200 is validated, unless the user explicitly accepts route-level-only risk.
- E2 click pending remains open until owner credentials are provided.
