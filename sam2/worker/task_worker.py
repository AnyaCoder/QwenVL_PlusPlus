import uuid
from copy import deepcopy
from queue import Queue
from threading import Thread

from loguru import logger

from config.settings import settings
from models.schemas import (SegmentBatchRequest, SegmentRequest,
                            VideoAnalysisRequest)
from services.segmentation_service import segmentation_service
from services.vision_service import vision_service

# 全局任务状态和队列
TASK_STATUS = {}
TASK_QUEUE = Queue(maxsize=settings.task_queue_maxsize)


def worker_loop():
    """工作线程循环，顺序执行队列任务"""
    while True:
        try:
            task = TASK_QUEUE.get()
            if task is None:
                break
            task_id, req, response_queue = task
            logger.info(f"Processing task: {task_id}")
            TASK_STATUS[task_id]["status"] = "processing"

            try:
                if isinstance(req, SegmentRequest):
                    if req.filename.endswith((".jpg", ".jpeg")):
                        result = segmentation_service.segment_image(req)
                    else:
                        # 视频帧处理（如果需要的话）
                        pass
                    TASK_STATUS[task_id]["frames"][req.frame_idx] = "done"
                elif isinstance(req, SegmentBatchRequest):
                    if req.filename.endswith((".jpg", ".jpeg")):
                        results = segmentation_service.segment_images(req)
                    else:
                        # 视频帧批量处理（如果需要的话）
                        pass
                    for idx, img_b64 in results.items():
                        TASK_STATUS[task_id]["frames"][idx] = "done"
                    result = results
                elif isinstance(req, VideoAnalysisRequest):
                    # 视频分析任务
                    result = vision_service.analyze_video(req)
                    TASK_STATUS[task_id]["result"] = result
                else:
                    raise ValueError(f"Unknown request type: {type(req)}")

                TASK_STATUS[task_id]["status"] = "done"
                if not isinstance(req, VideoAnalysisRequest):
                    TASK_STATUS[task_id]["result"] = result
                response_queue.put(("ok", result))

            except Exception as e:
                TASK_STATUS[task_id]["status"] = "error"
                TASK_STATUS[task_id]["result"] = str(e)
                response_queue.put(("error", str(e)))
                logger.error(f"Task {task_id} failed: {str(e)}")
            finally:
                TASK_QUEUE.task_done()
        except Exception as e:
            logger.error(f"[Worker Error] {e}")


def enqueue_task(req):
    """将任务放入队列并立即返回task_id"""
    if TASK_QUEUE.full():
        from fastapi import HTTPException

        raise HTTPException(status_code=429, detail="Queue is full, try again later.")

    task_id = str(uuid.uuid4())
    TASK_STATUS[task_id] = {"status": "queued", "result": None, "frames": {}}

    response_queue = Queue()
    TASK_QUEUE.put((task_id, req, response_queue))

    return {"status": "queued", "task_id": task_id}


def get_task_status(task_id: str):
    """获取任务状态"""
    if task_id not in TASK_STATUS:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Task ID not found")

    task_info = TASK_STATUS[task_id]
    if task_info["status"] in ["done", "error"]:
        r_info = deepcopy(task_info)
        del task_info
        return r_info

    return {"status": task_info["status"], "task_id": task_id}
