# Phase 2L-E5 Works Media Frontend Runtime Summary

## 1. Scope

This phase completed the build, frontend-only recreate, and basic runtime smoke validation for the `/works` preview/download frontend UI.

This phase does not include success-state DOM/Network validation, smoke work/object preparation, stream/range implementation, or E2 Canvas archive click-path validation.

The validated scope is limited to:

- frontend runtime deployment of the `/works` preview/download UI;
- runtime asset checks for the E5 frontend code paths;
- `/` and `/works` HTTP route smoke;
- anonymous works media preview/download authorization gate smoke;
- confirmation that non-frontend services were not recreated.

## 2. Code Baseline

- code commit: `60a2949f7f6c6ad10b13e50c59847002f8420d1f`
- message: `phase2l: add works media preview download ui`
- modified files in that code commit:
  - `frontend/src/services/works.js`
  - `frontend/src/views/WorksLibrary.vue`

## 3. Frontend Implementation Summary

The frontend implementation recorded by the runtime summary uses the authenticated fetch/blob approach for works media preview/download.

Confirmed implementation boundaries:

- uses authenticated fetch/blob requests;
- does not use raw URL / `window.open` / direct `a href` works media requests;
- preview/download calls go through works-scoped endpoints;
- does not use the `media.py` object_key route;
- does not place `object_key` in the browser URL;
- does not display full `object_key` values;
- uses `maskObjectKey` for object key display;
- cleans up Blob URLs;
- supports basic video/image/audio preview surfaces;
- shows an unsupported inline preview message for unknown media types;
- stream/range is not implemented, so video seek is not guaranteed.

## 4. Build / Deployment

- rollback tag: `aicon-demo-frontend:rollback-before-works-media-ui-60a2949`
- old frontend image: `sha256:8aa864ebf84dad11e41ded8a6bea1409e6d5fcb6dcdacc7ff34efbabf0225988`
- new frontend image: `sha256:6f710e37f8b1a6e3d3dee26d38ac0bda8c2122e95f9e568cd968ac2471b68cb3`
- build command: `sudo docker compose -f docker-compose.demo.yml build frontend`
- recreate command: `sudo docker compose -f docker-compose.demo.yml up -d --no-deps --force-recreate frontend`

Deployment result:

- only frontend was recreated;
- backend was not recreated;
- celery-worker was not recreated;
- celery-beat was not recreated;
- postgres was not recreated;
- redis was not recreated;
- minio was not recreated;
- no DB migration was run;
- no rollback was executed;
- no push was performed.

## 5. Runtime Assets

E5 UI is present in runtime assets.

Matched runtime files:

- `/usr/share/nginx/html/assets/WorksLibrary-Bv-6A4EB.js`
- `/usr/share/nginx/html/assets/works-D__qn9d0.js`

Matched symbols/text:

- `fetchWorkItemPreviewBlob`
- `fetchWorkItemDownloadBlob`
- `downloadWorkItemMedia`
- `maskObjectKey`
- preview/download permission/seek/inline preview text

The E5 UI runtime chunks do not contain:

- `/api/v1/media`
- `media/preview`
- `media/download`
- `media/stream`
- `api.openai.com`
- `Provider`

## 6. HTTP / Route Smoke

Runtime route smoke results:

- `/` returned `200`;
- `/works` returned `200`;
- anonymous preview returned `401`;
- anonymous download returned `401`.

Conclusion: the frontend is serving the new assets and the backend works media auth gate remains active.

This does not prove success-state DOM/Network preview/download because no active work sample exists in the current DB state.

## 7. Side Effects

E5-C side-effect review:

- no project files were changed during deployment;
- no DB writes were performed;
- no MinIO writes were performed;
- no MinIO deletes were performed;
- no Provider calls were performed;
- no official API calls were performed;
- no generation calls were performed;
- no compose calls were performed;
- no rollback was executed;
- no push was performed;
- `.env.demo` and `PHASE0_BASIC_AUTH.txt` remained untracked and were not read.

## 8. Not Completed

The following items remain explicitly not completed:

- success-state DOM/Network preview/download not validated;
- current DB has no active work sample:
  - `works_total=1`
  - `works_active=0`
  - `work_items_total=1`
  - `active_work_items=0`
- smoke work/object was not created in E5-C;
- frontend preview/download success-state needs separate smoke sample authorization or a real active work;
- stream/range not implemented;
- E2 Canvas archive click success path still pending;
- no push.

## 9. Recommended Next Step

Recommended next options:

- Option A: create E5-D0 smoke sample planning for DOM/Network success-state validation.
- Option B: if route/basic runtime validation is accepted, proceed to E5 summary closure.

Do not claim success-state DOM/Network until a valid active sample exists.

Continue forbidding the `media.py` object_key route for works media preview/download.

Plan stream/range separately if needed.

Keep the E2 Canvas archive click-path pending item open until it is separately validated.