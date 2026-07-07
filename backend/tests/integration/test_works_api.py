import base64
import json
import uuid
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

import pytest
from sqlalchemy import select

from src.models.canvas import CanvasDocument, CanvasGenerationType, CanvasItem, CanvasItemGeneration
from src.models.user import User
from src.models.work import Work, WorkItem

pytestmark = pytest.mark.integration

FINAL_OBJECT_KEY = "uploads/user/final-compose.mp4"

MEDIA_BYTES = b"fake works media bytes"


class FakeObjectResponse:
    def __init__(self, body: bytes):
        self.body = body
        self.closed = False
        self.released = False

    def stream(self, chunk_size):
        for index in range(0, len(self.body), chunk_size):
            yield self.body[index:index + chunk_size]

    def close(self):
        self.closed = True

    def release_conn(self):
        self.released = True


class FakeStorageClient:
    def __init__(self, objects=None):
        self.bucket_name = "test-bucket"
        self.objects = dict(objects or {})
        self.requested_keys = []
        self.get_object_calls = []
        self.put_calls = []
        self.delete_calls = []
        self.client = self

    def get_object(self, bucket_name, object_key, offset=0, length=0, **_kwargs):
        self.requested_keys.append(object_key)
        self.get_object_calls.append({"object_key": object_key, "offset": offset, "length": length})
        if bucket_name != self.bucket_name or object_key not in self.objects:
            raise RuntimeError("object not found")
        body = self.objects[object_key]
        end = None if not length else offset + length
        return FakeObjectResponse(body[offset:end])

    def stat_object(self, bucket_name, object_key, **_kwargs):
        if bucket_name != self.bucket_name or object_key not in self.objects:
            raise RuntimeError("object not found")
        return SimpleNamespace(
            size=len(self.objects[object_key]),
            content_type="video/mp4",
            metadata={},
            etag="test-etag",
            last_modified=None,
        )

    def put_object(self, *args, **kwargs):
        self.put_calls.append((args, kwargs))
        raise AssertionError("works media tests must not write storage")

    def remove_object(self, *args, **kwargs):
        self.delete_calls.append((args, kwargs))
        raise AssertionError("works media tests must not delete storage")


async def _fake_storage_client(storage):
    return storage


def install_fake_storage(monkeypatch, objects=None):
    storage = FakeStorageClient(objects)

    async def fake_get_storage_client():
        return await _fake_storage_client(storage)

    monkeypatch.setattr("src.api.v1.works.get_storage_client", fake_get_storage_client)
    return storage



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


def _stream_token_from_url(stream_url: str) -> str:
    parsed = urlparse(stream_url)
    values = parse_qs(parsed.query).get("token") or []
    assert values
    return values[0]


def _decoded_stream_token_payload(stream_url: str) -> dict:
    token = _stream_token_from_url(stream_url)
    payload_part = token.split(".", 1)[0]
    padded = payload_part + "=" * (-len(payload_part) % 4)
    return json.loads(base64.urlsafe_b64decode(padded.encode("ascii")))


async def create_stream_url(client, auth_headers, work, item) -> str:
    response = await client.post(
        f"/api/v1/works/{work['id']}/items/{item['id']}/stream-token",
        headers=auth_headers,
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["expires_in"] == 300
    assert payload["stream_url"]
    return payload["stream_url"]


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


async def archive_media_work(client, auth_headers, db_session):
    canvas_id, item_id = await create_canvas_final(client, auth_headers, db_session)
    response = await archive_work(client, auth_headers, canvas_id, item_id)
    assert response.status_code == 201
    payload = response.json()
    return payload, payload["items"][0]


@pytest.mark.asyncio
async def test_owner_can_preview_work_item_media(client, auth_headers, db_session, monkeypatch):
    storage = install_fake_storage(monkeypatch, {FINAL_OBJECT_KEY: MEDIA_BYTES})
    work, item = await archive_media_work(client, auth_headers, db_session)

    response = await client.get(
        f"/api/v1/works/{work['id']}/items/{item['id']}/preview",
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.content == MEDIA_BYTES
    assert response.headers["content-type"].startswith("video/mp4")
    assert "content-disposition" not in response.headers
    assert storage.requested_keys == [FINAL_OBJECT_KEY]
    assert storage.put_calls == []
    assert storage.delete_calls == []


@pytest.mark.asyncio
async def test_owner_can_download_work_item_media(client, auth_headers, db_session, monkeypatch):
    storage = install_fake_storage(monkeypatch, {FINAL_OBJECT_KEY: MEDIA_BYTES})
    work, item = await archive_media_work(client, auth_headers, db_session)

    response = await client.get(
        f"/api/v1/works/{work['id']}/items/{item['id']}/download",
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.content == MEDIA_BYTES
    assert response.headers["content-type"].startswith("video/mp4")
    assert response.headers["content-disposition"] == 'attachment; filename="final-compose.mp4"'
    assert storage.requested_keys == [FINAL_OBJECT_KEY]
    assert storage.put_calls == []
    assert storage.delete_calls == []


@pytest.mark.asyncio
async def test_work_item_media_requires_auth(client, auth_headers, db_session, monkeypatch):
    storage = install_fake_storage(monkeypatch, {FINAL_OBJECT_KEY: MEDIA_BYTES})
    work, item = await archive_media_work(client, auth_headers, db_session)

    preview = await client.get(f"/api/v1/works/{work['id']}/items/{item['id']}/preview")
    download = await client.get(f"/api/v1/works/{work['id']}/items/{item['id']}/download")

    assert preview.status_code == 401
    assert download.status_code == 401
    assert storage.requested_keys == []


@pytest.mark.asyncio
async def test_non_owner_cannot_access_work_item_media(client, auth_headers, db_session, monkeypatch):
    storage = install_fake_storage(monkeypatch, {FINAL_OBJECT_KEY: MEDIA_BYTES})
    work, item = await archive_media_work(client, auth_headers, db_session)
    second_headers = await create_second_user_headers(client)

    preview = await client.get(f"/api/v1/works/{work['id']}/items/{item['id']}/preview", headers=second_headers)
    download = await client.get(f"/api/v1/works/{work['id']}/items/{item['id']}/download", headers=second_headers)

    assert preview.status_code == 404
    assert download.status_code == 404
    assert storage.requested_keys == []


@pytest.mark.asyncio
async def test_deleted_work_item_media_returns_404(client, auth_headers, db_session, monkeypatch):
    storage = install_fake_storage(monkeypatch, {FINAL_OBJECT_KEY: MEDIA_BYTES})
    work, item = await archive_media_work(client, auth_headers, db_session)
    delete_response = await client.delete(f"/api/v1/works/{work['id']}", headers=auth_headers)
    assert delete_response.status_code == 200

    preview = await client.get(f"/api/v1/works/{work['id']}/items/{item['id']}/preview", headers=auth_headers)

    assert preview.status_code == 404
    assert storage.requested_keys == []


@pytest.mark.asyncio
async def test_wrong_work_item_media_id_returns_404(client, auth_headers, db_session, monkeypatch):
    storage = install_fake_storage(monkeypatch, {FINAL_OBJECT_KEY: MEDIA_BYTES})
    work, _item = await archive_media_work(client, auth_headers, db_session)

    response = await client.get(
        f"/api/v1/works/{work['id']}/items/{uuid.uuid4()}/preview",
        headers=auth_headers,
    )

    assert response.status_code == 404
    assert storage.requested_keys == []


@pytest.mark.asyncio
async def test_item_from_another_work_media_returns_404(client, auth_headers, db_session, monkeypatch):
    storage = install_fake_storage(monkeypatch, {FINAL_OBJECT_KEY: MEDIA_BYTES})
    first_work, _first_item = await archive_media_work(client, auth_headers, db_session)
    second_work, second_item = await archive_media_work(client, auth_headers, db_session)

    response = await client.get(
        f"/api/v1/works/{first_work['id']}/items/{second_item['id']}/preview",
        headers=auth_headers,
    )

    assert first_work["id"] != second_work["id"]
    assert response.status_code == 404
    assert storage.requested_keys == []


@pytest.mark.asyncio
async def test_blank_work_item_object_key_returns_404(client, auth_headers, db_session, monkeypatch):
    storage = install_fake_storage(monkeypatch, {FINAL_OBJECT_KEY: MEDIA_BYTES})
    work, item = await archive_media_work(client, auth_headers, db_session)
    db_item = await db_session.get(WorkItem, uuid.UUID(item["id"]))
    db_item.object_key = "  "
    await db_session.commit()

    response = await client.get(f"/api/v1/works/{work['id']}/items/{item['id']}/preview", headers=auth_headers)

    assert response.status_code == 404
    assert storage.requested_keys == []


@pytest.mark.asyncio
async def test_missing_storage_object_returns_404(client, auth_headers, db_session, monkeypatch):
    storage = install_fake_storage(monkeypatch, {})
    work, item = await archive_media_work(client, auth_headers, db_session)

    response = await client.get(f"/api/v1/works/{work['id']}/items/{item['id']}/preview", headers=auth_headers)

    assert response.status_code == 404
    assert storage.requested_keys == [FINAL_OBJECT_KEY]


@pytest.mark.asyncio
async def test_work_item_media_ignores_object_key_query(client, auth_headers, db_session, monkeypatch):
    storage = install_fake_storage(monkeypatch, {FINAL_OBJECT_KEY: MEDIA_BYTES, "uploads/evil.mp4": b"evil"})
    work, item = await archive_media_work(client, auth_headers, db_session)

    response = await client.get(
        f"/api/v1/works/{work['id']}/items/{item['id']}/preview?object_key=uploads/evil.mp4",
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.content == MEDIA_BYTES
    assert storage.requested_keys == [FINAL_OBJECT_KEY]



@pytest.mark.asyncio
async def test_owner_can_create_work_item_stream_token(client, auth_headers, db_session, monkeypatch):
    storage = install_fake_storage(monkeypatch, {FINAL_OBJECT_KEY: MEDIA_BYTES})
    work, item = await archive_media_work(client, auth_headers, db_session)

    response = await client.post(
        f"/api/v1/works/{work['id']}/items/{item['id']}/stream-token",
        headers=auth_headers,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["expires_in"] == 300
    assert payload["stream_url"].startswith(f"/api/v1/works/{work['id']}/items/{item['id']}/stream?token=")
    token_payload = _decoded_stream_token_payload(payload["stream_url"])
    assert set(token_payload) == {"user_id", "work_id", "item_id", "exp"}
    assert token_payload["work_id"] == work["id"]
    assert token_payload["item_id"] == item["id"]
    assert "object_key" not in token_payload
    assert storage.requested_keys == []


@pytest.mark.asyncio
async def test_owner_can_stream_work_item_media_without_range(client, auth_headers, db_session, monkeypatch):
    storage = install_fake_storage(monkeypatch, {FINAL_OBJECT_KEY: MEDIA_BYTES})
    work, item = await archive_media_work(client, auth_headers, db_session)
    stream_url = await create_stream_url(client, auth_headers, work, item)

    response = await client.get(stream_url)

    assert response.status_code == 200
    assert response.content == MEDIA_BYTES
    assert response.headers["accept-ranges"] == "bytes"
    assert response.headers["content-length"] == str(len(MEDIA_BYTES))
    assert response.headers["content-type"].startswith("video/mp4")
    assert storage.get_object_calls == [{"object_key": FINAL_OBJECT_KEY, "offset": 0, "length": 0}]
    assert storage.put_calls == []
    assert storage.delete_calls == []


@pytest.mark.asyncio
async def test_owner_can_stream_work_item_media_with_range(client, auth_headers, db_session, monkeypatch):
    storage = install_fake_storage(monkeypatch, {FINAL_OBJECT_KEY: MEDIA_BYTES})
    work, item = await archive_media_work(client, auth_headers, db_session)
    stream_url = await create_stream_url(client, auth_headers, work, item)

    response = await client.get(stream_url, headers={"Range": "bytes=0-3"})

    assert response.status_code == 206
    assert response.content == MEDIA_BYTES[:4]
    assert response.headers["accept-ranges"] == "bytes"
    assert response.headers["content-range"] == f"bytes 0-3/{len(MEDIA_BYTES)}"
    assert response.headers["content-length"] == "4"
    assert storage.get_object_calls == [{"object_key": FINAL_OBJECT_KEY, "offset": 0, "length": 4}]


@pytest.mark.asyncio
async def test_owner_can_stream_work_item_media_with_open_range(client, auth_headers, db_session, monkeypatch):
    storage = install_fake_storage(monkeypatch, {FINAL_OBJECT_KEY: MEDIA_BYTES})
    work, item = await archive_media_work(client, auth_headers, db_session)
    stream_url = await create_stream_url(client, auth_headers, work, item)

    response = await client.get(stream_url, headers={"Range": "bytes=5-"})

    assert response.status_code == 206
    assert response.content == MEDIA_BYTES[5:]
    assert response.headers["content-range"] == f"bytes 5-{len(MEDIA_BYTES) - 1}/{len(MEDIA_BYTES)}"
    assert response.headers["content-length"] == str(len(MEDIA_BYTES) - 5)
    assert storage.get_object_calls == [{"object_key": FINAL_OBJECT_KEY, "offset": 5, "length": len(MEDIA_BYTES) - 5}]


@pytest.mark.asyncio
async def test_owner_can_stream_work_item_media_with_suffix_range(client, auth_headers, db_session, monkeypatch):
    storage = install_fake_storage(monkeypatch, {FINAL_OBJECT_KEY: MEDIA_BYTES})
    work, item = await archive_media_work(client, auth_headers, db_session)
    stream_url = await create_stream_url(client, auth_headers, work, item)
    suffix_length = 5
    start = len(MEDIA_BYTES) - suffix_length

    response = await client.get(stream_url, headers={"Range": f"bytes=-{suffix_length}"})

    assert response.status_code == 206
    assert response.content == MEDIA_BYTES[-suffix_length:]
    assert response.headers["content-range"] == f"bytes {start}-{len(MEDIA_BYTES) - 1}/{len(MEDIA_BYTES)}"
    assert response.headers["content-length"] == str(suffix_length)
    assert storage.get_object_calls == [{"object_key": FINAL_OBJECT_KEY, "offset": start, "length": suffix_length}]


@pytest.mark.asyncio
async def test_invalid_stream_range_returns_416(client, auth_headers, db_session, monkeypatch):
    storage = install_fake_storage(monkeypatch, {FINAL_OBJECT_KEY: MEDIA_BYTES})
    work, item = await archive_media_work(client, auth_headers, db_session)
    stream_url = await create_stream_url(client, auth_headers, work, item)

    response = await client.get(stream_url, headers={"Range": "bytes=999-1000"})

    assert response.status_code == 416
    assert response.headers["accept-ranges"] == "bytes"
    assert response.headers["content-range"] == f"bytes */{len(MEDIA_BYTES)}"
    assert storage.get_object_calls == []


@pytest.mark.asyncio
async def test_stream_requires_valid_token(client, auth_headers, db_session, monkeypatch):
    storage = install_fake_storage(monkeypatch, {FINAL_OBJECT_KEY: MEDIA_BYTES})
    work, item = await archive_media_work(client, auth_headers, db_session)

    missing = await client.get(f"/api/v1/works/{work['id']}/items/{item['id']}/stream")
    invalid = await client.get(f"/api/v1/works/{work['id']}/items/{item['id']}/stream?token=invalid")

    assert missing.status_code in {401, 403}
    assert invalid.status_code in {401, 403}
    assert storage.requested_keys == []


@pytest.mark.asyncio
async def test_stream_rejects_expired_token(client, auth_headers, db_session, monkeypatch):
    storage = install_fake_storage(monkeypatch, {FINAL_OBJECT_KEY: MEDIA_BYTES})
    work, item = await archive_media_work(client, auth_headers, db_session)
    stream_url = await create_stream_url(client, auth_headers, work, item)
    token_payload = _decoded_stream_token_payload(stream_url)
    monkeypatch.setattr("src.api.v1.works.time.time", lambda: token_payload["exp"] + 1)

    response = await client.get(stream_url)

    assert response.status_code in {401, 403}
    assert storage.requested_keys == []


@pytest.mark.asyncio
async def test_stream_rejects_path_mismatch_token(client, auth_headers, db_session, monkeypatch):
    storage = install_fake_storage(monkeypatch, {FINAL_OBJECT_KEY: MEDIA_BYTES})
    first_work, first_item = await archive_media_work(client, auth_headers, db_session)
    second_work, second_item = await archive_media_work(client, auth_headers, db_session)
    stream_url = await create_stream_url(client, auth_headers, first_work, first_item)
    token = _stream_token_from_url(stream_url)

    response = await client.get(
        f"/api/v1/works/{second_work['id']}/items/{second_item['id']}/stream?token={token}"
    )

    assert response.status_code in {401, 403}
    assert storage.requested_keys == []


@pytest.mark.asyncio
async def test_non_owner_cannot_create_stream_token(client, auth_headers, db_session, monkeypatch):
    storage = install_fake_storage(monkeypatch, {FINAL_OBJECT_KEY: MEDIA_BYTES})
    work, item = await archive_media_work(client, auth_headers, db_session)
    second_headers = await create_second_user_headers(client)

    response = await client.post(
        f"/api/v1/works/{work['id']}/items/{item['id']}/stream-token",
        headers=second_headers,
    )

    assert response.status_code == 404
    assert storage.requested_keys == []


@pytest.mark.asyncio
async def test_wrong_item_cannot_create_stream_token(client, auth_headers, db_session, monkeypatch):
    storage = install_fake_storage(monkeypatch, {FINAL_OBJECT_KEY: MEDIA_BYTES})
    work, _item = await archive_media_work(client, auth_headers, db_session)

    response = await client.post(
        f"/api/v1/works/{work['id']}/items/{uuid.uuid4()}/stream-token",
        headers=auth_headers,
    )

    assert response.status_code == 404
    assert storage.requested_keys == []


@pytest.mark.asyncio
async def test_stream_ignores_object_key_query(client, auth_headers, db_session, monkeypatch):
    storage = install_fake_storage(monkeypatch, {FINAL_OBJECT_KEY: MEDIA_BYTES, "uploads/evil.mp4": b"evil"})
    work, item = await archive_media_work(client, auth_headers, db_session)
    stream_url = await create_stream_url(client, auth_headers, work, item)

    response = await client.get(f"{stream_url}&object_key=uploads/evil.mp4")

    assert response.status_code == 200
    assert response.content == MEDIA_BYTES
    assert storage.requested_keys == [FINAL_OBJECT_KEY]
