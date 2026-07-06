import uuid

import pytest
from sqlalchemy import select

from src.core.exceptions import BusinessLogicError, NotFoundError
from src.models.canvas import CanvasDocument, CanvasGenerationType, CanvasItem, CanvasItemGeneration
from src.models.work import Work, WorkItem
from src.services.work import WorkService

pytestmark = pytest.mark.unit

USER_ID = uuid.UUID("10000000-0000-0000-0000-000000000001")
OTHER_USER_ID = uuid.UUID("10000000-0000-0000-0000-000000000002")
CANVAS_ID = uuid.UUID("20000000-0000-0000-0000-000000000001")
OTHER_CANVAS_ID = uuid.UUID("20000000-0000-0000-0000-000000000002")
ITEM_ID = uuid.UUID("30000000-0000-0000-0000-000000000001")
OTHER_ITEM_ID = uuid.UUID("30000000-0000-0000-0000-000000000002")
GENERATION_ID = uuid.UUID("40000000-0000-0000-0000-000000000001")
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


async def seed_canvas_final(
    db_session,
    *,
    user_id=USER_ID,
    canvas_id=CANVAS_ID,
    item_id=ITEM_ID,
    generation_id=GENERATION_ID,
    final_object_key=FINAL_OBJECT_KEY,
    include_generation=True,
    compose=True,
    item_status="completed",
    item_type="video",
):
    document = CanvasDocument(id=canvas_id, user_id=user_id, title="Source Canvas", description=None)
    content = compose_content(final_object_key) if compose else {"result_video_object_key": final_object_key}
    output = compose_result(final_object_key) if compose else {"result_video_object_key": final_object_key}
    item = CanvasItem(
        id=item_id,
        document_id=canvas_id,
        item_type=item_type,
        title="Final Video",
        position_x=0,
        position_y=0,
        width=360,
        height=240,
        content_json=content,
        generation_config_json={},
        last_run_status=item_status,
        last_run_error=None,
        last_output_json=output,
        z_index=1,
    )
    db_session.add_all([document, item])
    if include_generation:
        generation = CanvasItemGeneration(
            id=generation_id,
            item_id=item_id,
            document_id=canvas_id,
            user_id=user_id,
            generation_type=CanvasGenerationType.VIDEO.value,
            request_payload_json=compose_request() if compose else {"model": "veo"},
            status="completed",
            result_payload_json=output,
            error_message=None,
        )
        db_session.add(generation)
    await db_session.commit()
    return document, item


async def create_work(db_session, **kwargs):
    await seed_canvas_final(db_session, **kwargs)
    service = WorkService(db_session)
    return await service.create_from_canvas_final(
        user_id=str(kwargs.get("user_id", USER_ID)),
        canvas_id=str(kwargs.get("canvas_id", CANVAS_ID)),
        canvas_item_id=str(kwargs.get("item_id", ITEM_ID)),
        title="Archived Work",
        description="A final compose result",
    )


@pytest.mark.asyncio
async def test_create_from_canvas_final_archives_compose_result(db_session):
    work = await create_work(db_session)

    assert work.user_id == USER_ID
    assert work.title == "Archived Work"
    assert work.status == "archived"
    assert work.cover_object_key == FINAL_OBJECT_KEY
    assert work.final_object_key == FINAL_OBJECT_KEY
    assert work.source_canvas_id == CANVAS_ID
    assert work.source_canvas_item_id == ITEM_ID
    assert work.source_generation_id == GENERATION_ID

    items = (await db_session.execute(select(WorkItem).where(WorkItem.work_id == work.id))).scalars().all()
    assert len(items) == 1
    assert items[0].role == "final"
    assert items[0].media_type == "video"
    assert items[0].object_key == work.final_object_key


@pytest.mark.asyncio
async def test_create_from_canvas_final_rejects_plain_completed_video(db_session):
    await seed_canvas_final(db_session, compose=False)
    service = WorkService(db_session)

    with pytest.raises(BusinessLogicError):
        await service.create_from_canvas_final(
            user_id=str(USER_ID),
            canvas_id=str(CANVAS_ID),
            canvas_item_id=str(ITEM_ID),
            title="Plain Video",
        )


@pytest.mark.asyncio
async def test_create_from_canvas_final_records_missing_generation_reason(db_session):
    work = await create_work(db_session, include_generation=False)

    assert work.source_generation_id is None
    assert work.metadata_json["reason"] == "source_generation_missing"


@pytest.mark.asyncio
async def test_create_from_canvas_final_rejects_non_owner_canvas(db_session):
    await seed_canvas_final(db_session, user_id=OTHER_USER_ID)
    service = WorkService(db_session)

    with pytest.raises(NotFoundError):
        await service.create_from_canvas_final(
            user_id=str(USER_ID),
            canvas_id=str(CANVAS_ID),
            canvas_item_id=str(ITEM_ID),
            title="Not Mine",
        )


@pytest.mark.asyncio
async def test_create_from_canvas_final_rejects_item_outside_canvas(db_session):
    document = CanvasDocument(id=CANVAS_ID, user_id=USER_ID, title="Canvas A", description=None)
    other_document = CanvasDocument(id=OTHER_CANVAS_ID, user_id=USER_ID, title="Canvas B", description=None)
    item = CanvasItem(
        id=ITEM_ID,
        document_id=CANVAS_ID,
        item_type="video",
        title="Final Video",
        position_x=0,
        position_y=0,
        width=360,
        height=240,
        content_json=compose_content(),
        generation_config_json={},
        last_run_status="completed",
        last_run_error=None,
        last_output_json=compose_result(),
        z_index=1,
    )
    db_session.add_all([document, other_document, item])
    await db_session.commit()
    service = WorkService(db_session)

    with pytest.raises(NotFoundError):
        await service.create_from_canvas_final(
            user_id=str(USER_ID),
            canvas_id=str(OTHER_CANVAS_ID),
            canvas_item_id=str(ITEM_ID),
            title="Wrong Canvas",
        )


@pytest.mark.asyncio
async def test_duplicate_archive_is_rejected(db_session):
    await create_work(db_session)
    service = WorkService(db_session)

    with pytest.raises(BusinessLogicError):
        await service.create_from_canvas_final(
            user_id=str(USER_ID),
            canvas_id=str(CANVAS_ID),
            canvas_item_id=str(ITEM_ID),
            title="Duplicate",
        )


@pytest.mark.asyncio
async def test_update_work_allows_only_metadata_fields(db_session):
    work = await create_work(db_session)
    service = WorkService(db_session)

    updated = await service.update_work(
        user_id=str(USER_ID),
        work_id=str(work.id),
        updates={"title": "Updated", "description": None, "status": "hidden", "cover_object_key": FINAL_OBJECT_KEY},
    )
    assert updated.title == "Updated"
    assert updated.description is None
    assert updated.status == "hidden"

    with pytest.raises(BusinessLogicError):
        await service.update_work(user_id=str(USER_ID), work_id=str(work.id), updates={"status": "deleted"})

    with pytest.raises(BusinessLogicError):
        await service.update_work(user_id=str(USER_ID), work_id=str(work.id), updates={"cover_object_key": "uploads/other.mp4"})


@pytest.mark.asyncio
async def test_delete_work_soft_deletes_without_removing_sources(db_session):
    work = await create_work(db_session)
    service = WorkService(db_session)

    deleted = await service.delete_work(user_id=str(USER_ID), work_id=str(work.id))
    assert deleted.status == "deleted"
    assert deleted.deleted_at is not None

    assert await db_session.get(Work, work.id) is not None
    assert (await db_session.execute(select(WorkItem).where(WorkItem.work_id == work.id))).scalar_one_or_none() is not None
    assert await db_session.get(CanvasItem, ITEM_ID) is not None
    assert await db_session.get(CanvasItemGeneration, GENERATION_ID) is not None

    works, total = await service.list_works(user_id=str(USER_ID), page=1, size=20)
    assert works == []
    assert total == 0


@pytest.mark.asyncio
async def test_get_work_item_media_returns_owned_item(db_session):
    work = await create_work(db_session)
    item = (await db_session.execute(select(WorkItem).where(WorkItem.work_id == work.id))).scalar_one()
    service = WorkService(db_session)

    media_work, media_item, object_key, media_type, filename = await service.get_work_item_media(
        user_id=str(USER_ID),
        work_id=str(work.id),
        item_id=str(item.id),
    )

    assert media_work.id == work.id
    assert media_item.id == item.id
    assert object_key == FINAL_OBJECT_KEY
    assert media_type == "video"
    assert filename == "final-compose.mp4"


@pytest.mark.asyncio
async def test_get_work_item_media_rejects_non_owner(db_session):
    work = await create_work(db_session)
    item = (await db_session.execute(select(WorkItem).where(WorkItem.work_id == work.id))).scalar_one()
    service = WorkService(db_session)

    with pytest.raises(NotFoundError):
        await service.get_work_item_media(user_id=str(OTHER_USER_ID), work_id=str(work.id), item_id=str(item.id))


@pytest.mark.asyncio
async def test_get_work_item_media_rejects_deleted_work(db_session):
    work = await create_work(db_session)
    item = (await db_session.execute(select(WorkItem).where(WorkItem.work_id == work.id))).scalar_one()
    work_id = str(work.id)
    item_id = str(item.id)
    service = WorkService(db_session)
    await service.delete_work(user_id=str(USER_ID), work_id=work_id)

    with pytest.raises(NotFoundError):
        await service.get_work_item_media(user_id=str(USER_ID), work_id=work_id, item_id=item_id)


@pytest.mark.asyncio
async def test_get_work_item_media_rejects_item_from_another_work(db_session):
    first_work = await create_work(db_session)
    second_work = await create_work(
        db_session,
        canvas_id=OTHER_CANVAS_ID,
        item_id=OTHER_ITEM_ID,
        generation_id=uuid.UUID("40000000-0000-0000-0000-000000000002"),
        final_object_key="uploads/user/other-compose.mp4",
    )
    second_item = (await db_session.execute(select(WorkItem).where(WorkItem.work_id == second_work.id))).scalar_one()
    service = WorkService(db_session)

    with pytest.raises(NotFoundError):
        await service.get_work_item_media(user_id=str(USER_ID), work_id=str(first_work.id), item_id=str(second_item.id))


@pytest.mark.asyncio
async def test_get_work_item_media_rejects_item_user_mismatch(db_session):
    work = await create_work(db_session)
    item = (await db_session.execute(select(WorkItem).where(WorkItem.work_id == work.id))).scalar_one()
    item.user_id = OTHER_USER_ID
    await db_session.flush()
    service = WorkService(db_session)

    with pytest.raises(NotFoundError):
        await service.get_work_item_media(user_id=str(USER_ID), work_id=str(work.id), item_id=str(item.id))


@pytest.mark.asyncio
async def test_get_work_item_media_rejects_blank_object_key(db_session):
    work = await create_work(db_session)
    item = (await db_session.execute(select(WorkItem).where(WorkItem.work_id == work.id))).scalar_one()
    item.object_key = "  "
    await db_session.flush()
    service = WorkService(db_session)

    with pytest.raises(NotFoundError):
        await service.get_work_item_media(user_id=str(USER_ID), work_id=str(work.id), item_id=str(item.id))
