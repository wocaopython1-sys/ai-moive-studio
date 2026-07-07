# Phase 2L-E5 Works Media Success-State Smoke Summary

## 1. Scope

This document records the Phase 2L-E5 frontend preview/download success-state DOM/Network smoke validation for works-scoped media endpoints.

This summary only covers `/works` preview/download success-state behavior, permission/error checks, cleanup, and boundaries observed in the E5-D1 smoke run. It does not include stream/range implementation, video seek/range validation, E2 Canvas archive click success-path validation, or push.

## 2. Baseline

- Baseline before summary: `c11a356d6f2269a4b937a2b1df862ac05edb33f1`.
- Prior summary commit: `phase2l: add works media frontend runtime summary`.
- Frontend `/works` preview/download UI was already deployed before this smoke summary.
- Backend works-scoped media preview/download endpoints were already deployed before this smoke summary.
- Runtime services remained running during validation.

## 3. Smoke Sample Setup

The E5-D1 smoke validation used an isolated temporary sample:

- Created isolated smoke owner.
- Created isolated smoke non-owner.
- Wrote one tiny smoke MinIO object.
- Object type: 1x1 PNG / `image/png`.
- Created one active smoke work.
- Created one final smoke work_item.
- `object_key` was reported only in masked form.
- Password, token, and cookie values were masked and were not output.
- No full `object_key`, password, token, or cookie was output.

The smoke sample was only used to validate the works-scoped preview/download frontend path and was removed after validation.

## 4. Backend Confirmation

Backend checks confirmed the works-scoped media endpoints and permission boundaries:

- owner preview: `200`.
- owner download: `200`.
- Preview `Content-Type`: `image/png`.
- Download `Content-Disposition`: `attachment`.
- anonymous preview/download: `401 / 401`.
- non-owner preview/download: `404 / 404`.
- Wrong item: `404`.
- `object_key query ignore`: `200`, and the response returned the object referenced by the DB `WorkItem.object_key` rather than trusting a query parameter.

No media.py object_key route was used for these checks.

## 5. Frontend DOM/Network Success-State

Frontend DOM/Network validation confirmed the success-state path:

- `/works` opened.
- Smoke work appeared in the list.
- Detail drawer opened.
- Preview button appeared.
- Download button appeared.
- `object_key` UI was masked.
- Preview Network URL:
  `/api/v1/works/{work_id}/items/{item_id}/preview`.
- Download Network URL:
  `/api/v1/works/{work_id}/items/{item_id}/download`.
- Authorization header existed, but its value was not output.
- Preview status: `200`.
- Download status: `200`.
- Download response included `Content-Disposition: attachment`.
- No `/api/v1/media` request appeared.
- No `object_key` URL appeared.
- No Provider, official API, generation, or compose request appeared.

This closes the E5 success-state DOM/Network preview/download smoke path for works-scoped media endpoints.

## 6. Cleanup

The E5-D1 smoke data was cleaned after validation:

- Smoke owner cleaned.
- Smoke non-owner cleaned.
- Smoke work cleaned.
- Smoke work_item cleaned.
- Smoke MinIO object cleaned.
- Old deleted work was not modified.

Cleanup readonly check after validation:

```text
e5d1_smoke_users=0
e5d1_smoke_works=0
e5d1_smoke_work_items=0
```

Repository and runtime state after cleanup:

- Tracked diff remained empty before this summary document was generated.
- Services remained healthy/running.

## 7. Boundaries / Side Effects

- No project files changed during the E5-D1 smoke run.
- No DB schema changes were made.
- No service build/restart/reload occurred during the smoke run.
- no push occurred.
- No Provider or official API calls occurred.
- No generation or compose calls occurred.
- No media.py object_key route was used.
- No full `object_key`, token, cookie, or password was output.
- `.env.demo` and `PHASE0_BASIC_AUTH.txt` remained untracked and were not read.

## 8. Not Completed

- stream/range not implemented.
- Video seek/range not validated.
- E2 Canvas archive click success path still pending.
- No push.

## 9. Recommended Next Step

- Proceed to E5 final summary closure or broader Phase 2L summary closure.
