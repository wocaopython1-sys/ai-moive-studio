# Phase 2L-E4 Works Media Owner Smoke Summary

## 1. Scope

This phase validates the works-scoped media preview/download endpoints for the owner success path, permission/error paths, object_key query ignore behavior, and smoke cleanup.

Included in this phase:
- owner preview/download success validation for works-scoped media endpoints.
- anonymous and non-owner permission validation.
- wrong item validation.
- object_key query ignore validation.
- cleanup validation for this phase's smoke DB rows, smoke users, and smoke MinIO object.

Explicitly not included in this phase:
- frontend /works preview/download integration.
- stream/range support.
- E2 Canvas archive click success re-validation.

## 2. Baseline

- current code baseline before summary: fa042a90e8704b6ea44998241ac455a7c703b80c
- prior E3 route runtime summary: phase2l: add works media route runtime summary
- DB revision: 030
- backend runtime already includes works-scoped preview/download endpoints.

## 3. Smoke Sample Setup

The E4-A smoke validation created the minimum sample required to test owner media access:

- created a smoke owner.
- created a smoke non-owner.
- wrote one very small smoke MinIO object.
- object size: 26 bytes.
- object prefix: smoke/works-media/e4a/.
- created one smoke work.
- created one smoke work_item.
- media_type: video.
- role: final.
- object_key remained masked throughout reporting; the full value was not output.
- password, token, and cookie values remained masked; real values were not output.

## 4. Owner Success Validation

Owner media access through works-scoped endpoints was validated:

- owner preview status: 200
- owner preview Content-Type: video/mp4
- owner preview body length: 26 bytes
- owner download status: 200
- owner download Content-Type: video/mp4
- owner download Content-Disposition: attachment
- owner download body length: 26 bytes

Conclusion: works-scoped media owner preview/download 200 is closed for the smoke sample.

## 5. Permission / Error Validation

Permission and error behavior was validated:

- anonymous preview/download: 401 / 401
- non-owner preview/download: 404 / 404
- wrong item: 404
- object_key query ignore: preview?object_key=some-other-key returned 200 and still used the object referenced by DB WorkItem.object_key.
- media.py object_key route was not used.

## 6. Cleanup

Cleanup completed for this phase's smoke data:

- smoke work_item cleaned.
- smoke work cleaned.
- smoke MinIO object cleaned.
- smoke users cleaned.

Cleanup verification:

- work_item_exists_after_cleanup=false
- work_exists_after_cleanup=false
- file_exists_after_cleanup=false
- works=0
- work_items=0
- stage_users=0

Additional cleanup boundaries:

- old smoke data was not cleaned.
- the existing deleted work was not modified.
- existing E2/E3 residual data was not modified.

## 7. Boundaries / Side Effects

This phase stayed inside the authorized smoke validation scope:

- project business code was not modified.
- DB schema was not modified.
- services were not restarted.
- no push was performed; current state is not pushed.
- Provider was not called.
- official API was not called.
- generation / compose was not called.
- media.py object_key route was not used.
- password/token/cookie/secret values were not output.
- .env.demo and PHASE0_BASIC_AUTH.txt contents were not read.
- no frontend preview/download implementation was added.
- no stream/range implementation was added.

## 8. Not Completed

The following items remain outside this phase:

- frontend /works preview/download is not integrated.
- stream/range is not implemented.
- E2 Canvas archive click success path remains pending.
- this branch has not been pushed.

## 9. Recommended Next Step

Recommended next step:

- proceed to frontend /works preview/download integration read-only planning.
- frontend must use works-scoped URLs:
  - /api/v1/works/{work_id}/items/{item_id}/preview
  - /api/v1/works/{work_id}/items/{item_id}/download
- do not use the bare media.py object_key route for works media.
- if video seek support is required, plan stream/range separately.
- keep E2 Canvas archive click pending until it is validated with a real Canvas final sample.
- do not push until explicitly requested.
