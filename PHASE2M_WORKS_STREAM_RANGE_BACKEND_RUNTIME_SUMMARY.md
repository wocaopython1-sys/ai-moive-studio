# Phase 2M Works Stream/Range Backend Runtime Summary

## 1. Scope

This summary records the Phase 2M backend runtime validation for Works scoped stream/range endpoints.

Included scope:

- Works scoped stream-token runtime validation.
- Works scoped stream endpoint runtime validation.
- Owner, non-owner, wrong item, token, range, and object_key query behavior.
- Smoke sample cleanup verification.

Not included in this phase:

- frontend video seek integration
- frontend stream URL integration
- push
- Provider / official API / generation / compose

## 2. Baseline

- HEAD: d2d86c07d06dc8ce326d3a6ab436ee6d0229a8d1
- Branch: phase2k-workflow-display-guards
- Backend runtime image: sha256:ab29e2eb3b147ca777ba4b537db94cbda3a797e8f581017fc057a4eda790e711
- Backend stream/range commit: d2d86c0 phase2m: add works scoped stream range endpoints

## 3. Smoke Sample

- owner username: phase2m_stream_smoke_owner_dc7e927c755d
- non-owner username: phase2m_stream_smoke_non_owner_dc7e927c755d
- work id: 27e987f6-3274-423a-8577-1bfb416e7b48
- work_item id: c3b30a1b-de5e-4481-b498-6fd38a9d02c5
- has_object_key: true
- object_key_prefix: phase2m_stream_smoke_
- object_size: 96
- content_type: video/mp4
- full object_key was not output

## 4. Auth / Token Result

- owner login status: 200
- non-owner login status: 200
- owner_token_exists: true
- non_owner_token_exists: true
- owner stream-token status: 200
- expires_in: 300
- stream_url_exists: true
- non-owner stream-token status: 404
- wrong item status: 404
- password, Bearer token, stream token, and cookie were not output

## 5. Stream Range Result

- no Range: 200
- no Range headers:
  - Content-Type: video/mp4
  - Content-Length: 96
  - Accept-Ranges: bytes
- Range bytes=0-9:
  - status: 206
  - Content-Range: bytes 0-9/96
  - Content-Length: 10
- Range bytes=10-:
  - status: 206
  - Content-Range: bytes 10-95/96
  - Content-Length: 86
- Range bytes=-10:
  - status: 206
  - Content-Range: bytes 86-95/96
  - Content-Length: 10
- invalid out-of-range:
  - status: 416
  - Content-Range: bytes */96
- multiple range:
  - status: 416
- missing token:
  - status: 401
- invalid token:
  - status: 401
- path mismatch:
  - status: 401
- object_key query ignored:
  - status: 206
  - still returned bytes 0-9/96
  - full object_key was not output

## 6. Forbidden / Not Observed

- no Provider call
- no official API call
- no generation call
- no compose call
- no password/token/cookie/object_key output
- no backend runtime 500 / Traceback

## 7. Cleanup Result

- smoke work_items cleaned
- smoke works cleaned
- smoke users cleaned
- smoke MinIO object deleted
- smoke active works count: 0
- smoke work_items count: 0
- smoke users count / inactive: 0 / 0
- no historical data was cleaned

Important cleanup note:

- cleanup script had a local SQLAlchemy .astext compatibility Traceback once
- cleanup was rerun successfully
- this was not a backend runtime 500
- backend API logs did not show runtime 500 / Traceback for the stream/range validation path

## 8. Final Judgment

- Works scoped stream/range backend runtime curl validation is closed.
- owner no Range 200 is closed.
- owner Range 206 is closed.
- invalid range 416 is closed.
- missing/invalid token 401 is closed.
- non-owner stream-token 404 is closed.
- wrong item 404 is closed.
- object_key query ignored is closed.
- frontend video seek is not validated yet.
- frontend stream URL integration is not implemented yet.
- this summary is local until committed and pushed separately.

## 9. Recommended Next Step

- commit this summary locally.
- then plan frontend stream URL integration as Phase 2M-H or equivalent.
- push only with explicit user authorization.