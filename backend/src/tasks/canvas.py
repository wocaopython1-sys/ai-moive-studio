from src.core.logging import get_logger
from src.tasks.app import celery_app
from src.tasks.base import async_task_decorator

logger = get_logger(__name__)


@celery_app.task(bind=True, max_retries=0, name="canvas.generate_text")
@async_task_decorator
async def generate_canvas_text(db_session, self, generation_id: str):
    from src.services.canvas import CanvasGenerationService

    logger.info("Celery任务开始: canvas.generate_text (generation_id=%s)", generation_id)
    service = CanvasGenerationService(db_session)
    result = await service.process_text_generation(generation_id)
    logger.info("Celery任务成功: canvas.generate_text (generation_id=%s)", generation_id)
    return result


@celery_app.task(bind=True, max_retries=0, name="canvas.generate_image")
@async_task_decorator
async def generate_canvas_image(db_session, self, generation_id: str):
    from src.services.canvas import CanvasGenerationService

    logger.info("Celery任务开始: canvas.generate_image (generation_id=%s)", generation_id)
    service = CanvasGenerationService(db_session)
    result = await service.process_image_generation(generation_id)
    logger.info("Celery任务成功: canvas.generate_image (generation_id=%s)", generation_id)
    return result


@celery_app.task(bind=True, max_retries=0, name="canvas.generate_video")
@async_task_decorator
async def generate_canvas_video(db_session, self, generation_id: str):
    from src.services.canvas import CanvasGenerationService

    logger.info("Celery任务开始: canvas.generate_video (generation_id=%s)", generation_id)
    service = CanvasGenerationService(db_session)
    result = await service.process_video_generation(generation_id)
    logger.info("Celery任务成功: canvas.generate_video (generation_id=%s)", generation_id)
    return result

@celery_app.task(bind=True, max_retries=0, name="canvas.compose_video")
@async_task_decorator
async def compose_canvas_video(db_session, self, generation_id: str):
    from src.services.canvas import CanvasService

    logger.info("Celery任务开始: canvas.compose_video (generation_id=%s)", generation_id)
    service = CanvasService(db_session)
    result = await service.process_video_compose(generation_id)
    logger.info("Celery任务成功: canvas.compose_video (generation_id=%s)", generation_id)
    return result
