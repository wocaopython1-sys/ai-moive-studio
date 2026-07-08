# Phase 2M Frontend Stream URL Range Seek Summary

## 1. Scope

This phase validates that Works video preview uses the backend-scoped stream URL instead of a blob preview URL, and that browser Network Range seek behavior is closed against the deployed runtime.

Included:

- Works video preview requests a scoped stream token.
- Works video preview assigns the returned stream URL directly to the video element.
- Browser Network validation confirms Range-based stream playback and seek.

Not included:

- Backend stream/range implementation, which was closed in the Phase 2M backend summary.
- Provider / official API / generation / compose calls.
- Push, which requires separate explicit authorization.

## 2. Baseline

- frontend implementation base HEAD: `15c113888a79c4ff3b967a508b72461c17d8ac32`
- backend runtime image: `sha256:ab29e2eb3b147ca777ba4b537db94cbda3a797e8f581017fc057a4eda790e711`
- frontend runtime image: `sha256:2a5f2e4fa4fabb61d72980826305fef1521f3518bd71cf8871562399148c6140`

## 3. Implementation

Modified files:

- `frontend/src/services/works.js`
- `frontend/src/views/WorksLibrary.vue`

Implementation notes:

- Added `createWorkItemStreamToken(workId, itemId)`.
- Video preview uses `stream-token` plus the returned `stream_url`.
- Image preview remains blob-based.
- Audio preview remains blob-based.
- Download remains blob-based through the existing download endpoint.
- Blob URL cleanup and stream URL cleanup are separated.
- `stream_url` is not passed to `URL.revokeObjectURL`.
- `object_key` masking remains unchanged.
- No `console.log` output was added for token, stream URL, or object key values.

## 4. Runtime Deployment

- frontend rollback tag: `aicon-demo-frontend:rollback-before-2m-stream-url-15c1138`
- old frontend image: `sha256:a7979c3a6775ad3e17e28f1e044638bf82a0664514afa3ea0e0ef571d6d0d61d`
- new frontend image: `sha256:2a5f2e4fa4fabb61d72980826305fef1521f3518bd71cf8871562399148c6140`
- Only frontend was built/recreated.
- Backend, postgres, redis, minio, celery-worker, and celery-beat were not recreated.
- `/` returned 200.
- `/works` returned 200.

## 5. Browser Range Seek Validation

- smoke video source: generated with backend container `/usr/bin/ffmpeg`.
- The first small 17KB MP4 fully buffered on the first Range request, so seek did not trigger a second Range.
- The smoke object was replaced with a 4.7MB MP4 and browser network throttling was enabled for final validation.
- object_size: `4700306`
- content_type: `video/mp4`
- owner login status: success
- `/works` showed the smoke work.
- Detail drawer opened.
- Video preview clicked.
- video_src_is_stream: true
- video_src_has_token: true
- video_src_prefix: `/api/v1/works/`
- full video src was not output.
- stream token was not output.
- stream-token status: 200
- initial video stream status: 206
- initial request had Range: true
- seek triggered Range: true
- seek Range status: 206
- seek Content-Range: exists
- seek Accept-Ranges: bytes

## 6. Cleanup Result

- smoke work_item cleaned.
- smoke work cleaned.
- smoke user cleaned.
- smoke MinIO object cleaned.
- smoke active works count: 0
- smoke work_items count: 0
- smoke users count / inactive: 0 / 0
- smoke object prefix count: 0
- No historical data was cleaned.

## 7. Forbidden / Not Observed

- no Provider call
- no official API call
- no generation call
- no compose call
- no password output
- no Bearer token output
- no stream token output
- no cookie output
- no full object_key output
- no full video src output
- backend runtime logs had no 500 / Traceback / exception
- frontend logs had no obvious error / exception

## 8. Final Judgment

- frontend stream URL integration is closed.
- browser Network Range seek validation is closed.
- video src stream URL validation is closed.
- image/audio preview remain blob-based.
- download remains unchanged.
- Frontend changes are local until committed and pushed separately.

## 9. Remaining Items

- Pre-2M-M status: frontend changes still need commit in this stage.
- push still requires explicit user authorization.
