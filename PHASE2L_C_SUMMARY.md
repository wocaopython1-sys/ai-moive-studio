# Phase 2L-C Summary: Canvas to Asset Library Search Entry

## 1. Phase Goal

Phase 2L-C implements the minimal frontend path from Canvas to the asset library.

Scope:
- Canvas side enters the asset library and searches for the same file by `object_key`.
- Frontend-only minimal implementation.
- No portfolio/library product restructure.
- No final MP4 strong association.
- No full asset precise-location system.
- No model generation is triggered.

## 2. Important Boundaries

- `object_key` is only used to search for the same file.
- `object_key` does not prove Canvas source ownership.
- The implementation does not infer Canvas source from `object_key`.
- The implementation does not infer final status from `object_key`.
- The implementation does not infer Canvas source from filename or path.
- The implementation does not infer final status from filename or path.
- Nodes without `object_key` do not show a misleading library entry.
- No new API was added.
- No new DB table or field was added.
- Backend code was not modified.
- `.env.demo` was not read.
- `PHASE0_BASIC_AUTH.txt` was not read.

## 3. Completed Changes

Changed files:
- `frontend/src/views/AssetsLibrary.vue`
- `frontend/src/views/canvas/CanvasEditor.vue`

`frontend/src/views/AssetsLibrary.vue`:
- Added route query receiving for `route.query.search`.
- Added route query receiving for `route.query.q`.
- Added `applyRouteSearchQuery()`.
- Writes `search` / `q` into the existing `searchText` field.
- Calls the existing `loadAssets()` when route query changes.
- Continues to reuse the existing `q: searchText.value` request parameter.

`frontend/src/views/canvas/CanvasEditor.vue`:
- Reuses existing `resolveObjectKeyFromItem()` for media node keys.
- Adds `selectedMediaLibrarySearchKey` and `canOpenSelectedInLibrary`.
- Shows `在素材库查看` only for selected image/video nodes with a reliable `object_key`.
- Adds `data-testid="open-selected-in-library"`.
- Clicking the entry navigates to `/library?search=<object_key>`.
- Nodes without `object_key` do not show the entry.
- Existing preview, download, copy URL, and save-to-library behavior was kept unchanged.

## 4. Verification

Fresh verification results from this round:
- `git diff --check`: passed with no output.
- Frontend production build passed: Vite build completed, `built in 11.87s`.
- Frontend was rebuilt.
- Only `aicon-demo-frontend` was recreated.
- Backend, celery, postgres, and redis were not restarted.
- `backend` remained `Up 2 days`.
- `postgres` and `redis` remained `Up 5 days`.
- `http://127.0.0.1:19180/library`: 200.
- `http://127.0.0.1:19180/library?search=test`: 200.
- `http://127.0.0.1:19180/library?q=test`: 200.
- `http://127.0.0.1:19180/canvas`: 200.
- `http://127.0.0.1:19180/tasks`: 200.
- `http://127.0.0.1:19180/dashboard`: 200.
- `http://127.0.0.1:19180/health/`: 200.
- Frontend/backend/celery latest 100 log lines had no `ERROR`, `Traceback`, or `Exception` matches.
- Diff security scan passed.
- No generate / retry / refresh / resume / compose action was triggered.

## 5. Required Limitations To Record

- Public `https://aicon.geminiproo.shop/library?search=test` returned 401 Basic Auth.
- The specified public Canvas URL also returned 401 Basic Auth.
- `.env.demo` was not read.
- `PHASE0_BASIC_AUTH.txt` was not read.
- Chrome DOM verification was not completed because Basic Auth blocked the page.
- Filling the search box from `search` / `q` was not verified through public Chrome DOM.
- The `在素材库查看` button was not verified through public Chrome DOM.
- Evidence for this round is source code, local 200 checks, production build, bundle/source markers, logs, git diff, and security scans.
- Chrome DOM must not be treated as passed for this round.

## 6. Security And Scope

- No model generation was triggered.
- No API was added.
- No DB change was added.
- Backend code was not modified.
- Dockerfile was not modified.
- Migrations were not modified.
- Nginx, Cloudflare, New API, and media-gateway were not modified.
- Screenshots were not added.
- Temporary scripts were not added.
- `.env.demo` remains untracked and must not be committed.
- `PHASE0_BASIC_AUTH.txt` remains untracked and must not be committed.
- Diff scan found no key/token/password/base64 leak.
- Diff scan found no hardcoded real UUID, real `object_key`, or `user_id`.

## 7. Not Completed But Non-Blocking

- Chrome DOM verification should be repeated after Basic Auth access is available.
- Full asset precise-location system was not implemented.
- `object_key` search result uniqueness is not guaranteed.
- Final MP4 portfolio loop was not implemented.
- Portfolio/library restructure was not implemented.
- Backend reverse lookup API was not added.
- DB association table was not added.
- Phase 2L-D or Phase 2L final summary should be planned separately.

## 8. Patch Directory

Patch directory:
- `/opt/backups/aicon-demo-20260704-phase2l-c-patches`

Patch files:
- `phase2l-c-all.diff`
- `phase2l-c-assets-library-query-search.diff`
- `phase2l-c-canvas-open-library.diff`
- `phase2l-c-summary.diff`

## 9. Rollback

Rollback options:
- Revert the future Phase 2L-C commit to return to `93c7df6`.
- Or apply the generated patches in reverse.

## 10. Recommended Next Step

- Run a pre-commit closure audit first.
- Commit only after the audit passes.
- Discuss Phase 2L final summary separately.
- Do not start a portfolio/library restructure immediately.
