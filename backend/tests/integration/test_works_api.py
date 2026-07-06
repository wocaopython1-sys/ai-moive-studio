import uuid

import pytest
from sqlalchemy import select

from src.models.canvas import CanvasDocument, CanvasGenerationType, CanvasItem, CanvasItemGeneration
from src.models.user import User
from src.models.work import Work, WorkItem

pytestmark = pytest.mark.integration

FINAL_OBJECT_KEY = "uploads/user/final-compose.mp4"


def compose_content(object_key=FINAL_OBJECT_KEY):
    return {
        "result_video_object_key": object_key,
        "compose_mode": "concat",
        "compose_source_item_ids": ["source-a", "source-b"],
        "clip_count": 2,
    }


def compose_result(object_key=FINAL_OBJECT_KEY):
    return {
        "result_video_object_key": object_key,
        "provider": "local",
        "provider_response": {"provider": "local", "tool": "ffmpeg", "mode": "concat"},
        "compose_source_item_ids": ["source-a", "source-b"],
        "clip_count": 2,
    }


def compose_request():
    return {
        "provider": "local",
        "model": "ffmpeg-concat",
        "options": {"mode": "concat", "source_item_ids": ["source-a", "source-b"], "clip_count": 2},
    }


async def current_user_id(db_session):
    result = await db_session.execute(select(User).where(User.username == "testuser"))
    return result.scalar_one().id


async def create_second_user_headers(client):
    await client.post(
        "/api/v1/auth/register",
        json={
            "username": "seconduser",
            "email": "second@example.com",
            "password": "testpassword123",
            "display_name": "Second User",
        },
    )
    login_response = await client.post(
        "/api/v1/auth/login",
        data={"username": "seconduser", "password": "testpassword123"},
    )
    assert login_response.status_code == 200
    return {"Authorization": f"Bearer {login_response.json()['access_token']}"}


async def create_canvas_final(client, auth_headers, db_session, *, compose=True, include_generation=True):
    create_response = await client.post("/api/v1/canvas-documents", headers=auth_headers, json={"title": "Works Canvas"})
    assert create_response.status_code == 201
    canvas_id = create_response.json()["id"]
    item_id = str(uuid.uuid4())
    content = compose_content() if compose else {"result_video_object_key": FINAL_OBJECT_KEY}
    output = compose_result() if compose else {"result_video_object_key": FINAL_OBJECT_KEY}
    save_response = await client.put(
        f"/api/v1/canvas-documents/{canvas_id}/graph",
        headers=auth_headers,
        json={
            "items": [
                {
                    "id": item_id,
                    "item_type": "video",
                    "title": "Final Compose",
                    "position_x": 0,
                    "position_y": 0,
                    "width": 360,
                    "height": 240,
                    "z_index": 1,
                    "content": content,
                    "generation_config": {},
                    "last_run_status": "completed",
                    "last_output": output,
                }
            ],
            "connections": [],
        },
    )
    assert save_response.status_code == 200
    user_id = await current_user_id(db_session)
    if include_generation:
        generation = CanvasItemGeneration(
            item_id=uuid.UUID(item_id),
            document_id=uuid.UUID(canvas_id),
            user_id=user_id,
            generation_type=CanvasGenerationType.VIDEO.value,
            request_payload_json=compose_request() if compose else {"model": "veo"},
            status="completed",
            result_payload_json=output,
            error_message=None,
        )
        db_session.add(generation)
        await db_session.commit()
    return canvas_id, item_id


async def archive_work(client, auth_headers, canvas_id, item_id, title="Archived Work"):
    return await client.post(
        "/api/v1/works/from-canvas-final",
        headers=auth_headers,
        json={"canvas_id": canvas_id, "canvas_item_id": item_id, "title": title},
    )


@pytest.mark.asyncio
async def test_archive_compose_final_and_fetch_detail(client, auth_headers, db_session):
    canvas_id, item_id = await create_canvas_final(client, auth_headers, db_session)

    response = await archive_work(client, auth_headers, canvas_id, item_id)

    assert response.status_code == 201
    payload = response.json()
    assert payload["title"] == "Archived Work"
    assert payload["status"] == "archived"
    assert payload["cover_object_key"] == FINAL_OBJECT_KEY
    assert payload["final_object_key"] == FINAL_OBJECT_KEY
    assert payload["source_canvas_id"] == canvas_id
    assert payload["source_canvas_item_id"] == item_id
    assert payload["items"][0]["role"] == "final"
    assert payload["items"][0]["object_key"] == FINAL_OBJECT_KEY

    detail_response = await client.get(f"/api/v1/works/{payload['id']}", headers=auth_headers)
    assert detail_response.status_code == 200
    assert detail_response.json()["items"][0]["object_key"] == FINAL_OBJECT_KEY


@pytest.mark.asyncio
async def test_list_works_returns_only_current_user_items(client, auth_headers, db_session):
    canvas_id, item_id = await create_canvas_final(client, auth_headers, db_session)
    first_response = await archive_work(client, auth_headers, canvas_id, item_id, title="Mine")
    assert first_response.status_code == 201

    second_headers = await create_second_user_headers(client)
    list_response = await client.get("/api/v1/works", headers=second_headers)
    assert list_response.status_code == 200
    assert list_response.json()["total"] == 0

    own_list_response = await client.get("/api/v1/works", headers=auth_headers)
    assert own_list_response.status_code == 200
    assert own_list_response.json()["total"] == 1
    assert own_list_response.json()["works"][0]["title"] == "Mine"


@pytest.mark.asyncio
async def test_non_owner_work_and_canvas_access_return_404(client, auth_headers, db_session):
    canvas_id, item_id = await create_canvas_final(client, auth_headers, db_session)
    response = await archive_work(client, auth_headers, canvas_id, item_id)
    assert response.status_code == 201
    work_id = response.json()["id"]
    second_headers = await create_second_user_headers(client)

    assert (await client.get(f"/api/v1/works/{work_id}", headers=second_headers)).status_code == 404
    assert (await archive_work(client, second_headers, canvas_id, item_id)).status_code == 404


@pytest.mark.asyncio
async def test_archive_rejects_item_that_does_not_belong_to_canvas(client, auth_headers, db_session):
    canvas_id, item_id = await create_canvas_final(client, auth_headers, db_session)
    other_canvas_response = await client.post("/api/v1/canvas-documents", headers=auth_headers, json={"title": "Other"})
    assert other_canvas_response.status_code == 201

    response = await archive_work(client, auth_headers, other_canvas_response.json()["id"], item_id)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_archive_rejects_non_compose_video(client, auth_headers, db_session):
    canvas_id, item_id = await create_canvas_final(client, auth_headers, db_session, compose=False)

    response = await archive_work(client, auth_headers, canvas_id, item_id)
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_patch_whitelist_and_delete_soft_delete(client, auth_headers, db_session):
    canvas_id, item_id = await create_canvas_final(client, auth_headers, db_session)
    response = await archive_work(client, auth_headers, canvas_id, item_id)
    assert response.status_code == 201
    work_id = response.json()["id"]

    patch_response = await client.patch(
        f"/api/v1/works/{work_id}",
        headers=auth_headers,
        json={"title": "Updated", "status": "hidden", "cover_object_key": FINAL_OBJECT_KEY},
    )
    assert patch_response.status_code == 200
    assert patch_response.json()["title"] == "Updated"
    assert patch_response.json()["status"] == "hidden"

    forbidden_patch = await client.patch(
        f"/api/v1/works/{work_id}",
        headers=auth_headers,
        json={"final_object_key": "uploads/forbidden.mp4"},
    )
    assert forbidden_patch.status_code == 422

    delete_response = await client.delete(f"/api/v1/works/{work_id}", headers=auth_headers)
    assert delete_response.status_code == 200
    list_response = await client.get("/api/v1/works", headers=auth_headers)
    assert list_response.status_code == 200
    assert list_response.json()["total"] == 0

    work = await db_session.get(Work, uuid.UUID(work_id))
    assert work is not None
    assert work.status == "deleted"
    assert work.deleted_at is not None
    assert (await db_session.execute(select(WorkItem).where(WorkItem.work_id == work.id))).scalar_one_or_none() is not None
    assert await db_session.get(CanvasItem, uuid.UUID(item_id)) is not None
    assert (await db_session.execute(select(CanvasItemGeneration).where(CanvasItemGeneration.item_id == uuid.UUID(item_id)))).scalar_one_or_none() is not None


@pytest.mark.asyncio
async def test_duplicate_archive_and_missing_generation_reason(client, auth_headers, db_session):
    canvas_id, item_id = await create_canvas_final(client, auth_headers, db_session, include_generation=False)
    response = await archive_work(client, auth_headers, canvas_id, item_id)
    assert response.status_code == 201
    assert response.json()["source_generation_id"] is None
    assert response.json()["metadata_json"]["reason"] == "source_generation_missing"

    duplicate = await archive_work(client, auth_headers, canvas_id, item_id)
    assert duplicate.status_code == 400
