# Phase 2L-D5 Works Backend Runtime Summary

## 1. Scope

Phase 2L-D5 only closes the works library backend runtime path.

Completed scope:
- Works backend schema was migrated on the real DB.
- Backend runtime image was rebuilt and deployed for backend, celery-worker, and celery-beat.
- Works API runtime smoke tests were executed for authentication, owner isolation, basic CRUD, and from-canvas-final.

Out of scope:
- Frontend /works page is not implemented.
- Canvas "archive as work" button is not implemented.
- Works-specific media preview/download permission API is not implemented.
- media.py was not changed.
- Nginx, Cloudflare, New API, and media-gateway were not changed.
- No push was performed. Current state is not pushed.

## 2. Final Baseline

- Code commit: 446776736c13c2ca261dd8c8abd5909a7e267ac8
- Backend commit message: phase2l: add works library backend
- DB revision: 030
- Deployment compose: docker-compose.demo.yml
- Backend image after deploy: sha256:282b60a915da66e460cbe2588549db2ef069862e591a01def9fab5cb07ba0275
- Rollback image tag: aicon-demo-backend:rollback-before-works-030-4467767
- Push status: not pushed

## 3. DB Migration Result

Real DB migration was executed to revision 030.

Confirmed results:
- alembic_version is 030.
- works table exists.
- work_items table exists.
- Works-related indexes exist.
- Works-related constraints exist.

Backup before real migration:
- /opt/backups/aicon-demo-20260706-before-real-works-030/aicon_db_before_real_030_create_works_tables.dump

Rollback / downgrade status:
- No alembic downgrade was executed.
- No manual SQL write was executed.
- No DB schema change was performed after migration 030.

## 4. Backend Runtime Deployment

Backend runtime deployment was completed after DB migration.

Deployment result:
- backend was rebuilt and recreated.
- celery-worker was recreated.
- celery-beat was recreated.
- backend is running and healthy.
- celery-worker is running.
- celery-beat is running.

New backend image:
- sha256:282b60a915da66e460cbe2588549db2ef069862e591a01def9fab5cb07ba0275

Rollback tag:
- aicon-demo-backend:rollback-before-works-030-4467767

Services not restarted or recreated:
- frontend
- postgres
- redis
- minio

Configuration not changed:
- Nginx
- Cloudflare
- New API
- media-gateway

Runtime code confirmation:
- /app/src/api/v1/works.py exists in backend container.
- /app/src/services/work.py exists in backend container.
- /app/src/models/work.py exists in backend container.
- /app/migrations/versions/030_create_works_tables.py exists in backend container.
- works router is registered with prefix /works.

## 5. Runtime API Smoke Result

Runtime smoke tests were executed against http://127.0.0.1:19181.

Results:
- GET /health/ returned 200.
- Anonymous GET /api/v1/works returned 401.
- Anonymous GET /api/v1/works was not 404.
- Anonymous GET /api/v1/works was not 500.
- Authenticated GET /api/v1/works?page=1&size=20 returned 200.
- POST /api/v1/works/from-canvas-final returned 201.
- GET /api/v1/works/{work_id} returned 200.
- PATCH /api/v1/works/{work_id} returned 200.
- DELETE /api/v1/works/{work_id} returned 200.
- GET list after delete returned 200 and did not include the deleted work.
- Non-owner GET returned 404.
- Non-owner PATCH returned 404.
- Non-owner DELETE returned 404.
- Random UUID GET returned 404.
- No 500 was observed during works smoke tests.

Important limitation:
- from-canvas-final was verified with an API-constructed smoke Canvas final sample.
- A real historical compose final sample was not validated in this phase.

## 6. Test Data Residue

The smoke test intentionally used public API paths and did not write SQL manually.

Residue confirmed:
- Created 2 smoke users.
- Created 1 smoke work: 30ae2cd1-872f-412e-a00d-57d8238536a9.
- The smoke work was soft deleted.
- The smoke work remains in works with status=deleted and deleted_at set.
- work_items keeps 1 row with role=final for the smoke work.
- The smoke Canvas document was deleted through API.
- No MinIO file was created.
- No Provider was called.

Cleanup policy:
- These residues were not cleaned in this phase.
- Cleaning smoke users or soft-deleted work data requires separate explicit authorization.

## 7. Security / Permission Result

Confirmed permission behavior:
- Works API requires Bearer authentication.
- Anonymous access is rejected with 401.
- Non-owner access returns 404.
- Random UUID returns 404.
- Soft delete works as intended.

Security boundary:
- object_key is not an authorization source.
- object_key must not be treated as a download permission grant.
- Works media preview/download permission is not implemented yet.
- Frontend must not directly rely on object_key for unauthorized media access.

Secret handling:
- Tokens were masked during smoke testing.
- No real token, password, cookie, DB URL, or secret was output.
- .env.demo and PHASE0_BASIC_AUTH.txt were not read.

## 8. Remaining Work

Not completed in 2L-D5:
- Frontend /works page is not implemented.
- Canvas final "archive as work" button is not implemented.
- Works-specific media preview/download permission API is not implemented.
- Basic Auth DOM verification is not completed.
- Current state is not pushed.
- Real historical compose final sample verification is not completed.
- Only an API-constructed smoke final was verified.

Known caution:
- Do not claim frontend works library completion from this phase.
- Do not claim media preview/download completion from this phase.
- Do not claim real historical final sample coverage from this phase.

## 9. Recommended Next Step

Before entering 2L-E implementation, run 2L-E0 read-only planning.

2L-E0 should decide:
- Whether to implement works-specific media permission API before frontend.
- The minimal /works page scope.
- The Canvas archive button scope.
- The frontend acceptance path.
- Whether smoke data cleanup is needed, and if yes, under separate explicit authorization.

Recommended next action:
- Start 2L-E0 as read-only planning.
- Do not directly implement frontend.
- Do not push until the user explicitly authorizes push.
