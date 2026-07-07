# Phase 2L-E2 Canvas Archive Revive Summary

## 1. Scope

This revive stage closed the previously pending real browser DOM/Network validation for the E2 Canvas archive click success path.

This stage did not include a repeated archive error-state fix, stream/range implementation, Provider calls, official API calls, generation calls, compose calls, MinIO writes/deletes, DB schema changes, service restart, or push.

## 2. Baseline

- baseline HEAD: 9d659990ef209468d16694100c071f6c60ea4d99
- branch: phase2k-workflow-display-guards
- target Canvas: 60aaebb2-1eed-44e7-b718-e6015b2d4c2d
- actual archived item: bbdd4c41-dfbf-4de7-96df-e80cdbe81985
- archived item title: Phase2J fill_missing final compose
- owner login: manual browser login
- password/token/cookie were not output
- object_key was not output

## 3. Success Path Result

- Canvas opened successfully in a real browser session.
- The final video item was selected.
- The archive button appeared for the selected final video item.
- The archive action was clicked.
- Network captured POST /api/v1/works/from-canvas-final.
- Authorization header existed, but its value was not output.
- response status: 201
- created work: c85fc544-0f9c-455a-a82d-0cb6752dbd89
- created work_item: 741853b8-aff0-400c-a8e9-ff8f27a7fe9d
- no Provider / official API / generation / compose requests were observed during the successful archive path.
- no media.py object_key route was used as Works permission basis.
- object_key was not output.

## 4. /works Display Result

- The new work appeared in the /works list.
- The detail drawer opened.
- The work_item was visible.
- object_key UI was masked/truncated.
- Preview/download buttons appeared in the detail drawer.
- Preview/download buttons were not clicked in this E2 revive run.

## 5. Cleanup Result

- The created work was soft deleted.
- deleted work id: c85fc544-0f9c-455a-a82d-0cb6752dbd89
- active_for_item=0
- work_item kept: 741853b8-aff0-400c-a8e9-ff8f27a7fe9d
- MinIO was not deleted.
- Historical data was not hard deleted.
- Project files remained unchanged during E2-REVIVE-A.
- Tracked diff remained empty before this summary document was created.

## 6. Repeated Archive Error-State Result

- repeated archive error-state was not closed.
- UI still showed the archive button when selecting the same node.
- Clicking repeated archive entered the archiving state and then recovered.
- Backend logs did not show a second POST /api/v1/works/from-canvas-final.
- DB active count did not increase.
- Browser console showed Persist canvas item failed.
- No 400 / already-archived API evidence was captured.
- This should be handled as a separate follow-up if full duplicate error-state coverage is required.

## 7. Still Pending / Not Included

- repeated archive error-state remains pending.
- stream/range not implemented.
- video seek/range not validated.
- media.py object_key route remains forbidden for Works.
- no push in this run.

## 8. Recommended Next Step

- If only the success path was required, E2 Canvas archive click success path can be considered closed.
- If full duplicate error-state coverage is required, plan a separate E2 duplicate archive error-state investigation.
- Do not mix stream/range into E2 revive.
- Do not reintroduce media.py object_key route for Works.
- Push only when the user explicitly authorizes it.