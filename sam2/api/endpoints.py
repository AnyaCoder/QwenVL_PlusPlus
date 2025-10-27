import logging
import os

from config.settings import settings
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from models.schemas import (ScanFolderRequest, SegmentBatchRequest,
                            SegmentRequest, VideoAnalysisRequest,
                            VideoAnalysisResponse, VisionAnalysisRequest,
                            VisionAnalysisResponse)
from services.file_service import scan_folder_for_frames
from worker.task_worker import enqueue_task, get_task_status


class RouteFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        """record.args: ('127.0.0.1:42770', 'GET', '/task_status/7431d23a-a898-4151-b2e8-00d1057afb18', '1.1', 200)"""
        path = record.args[2] if len(record.args) >= 3 else ""
        status = record.args[4] if len(record.args) >= 5 else -1

        return not (path.startswith("/task_status/") and status == 200)


for handler in logging.getLogger("uvicorn.access").handlers:
    handler.addFilter(RouteFilter())


def setup_routes(app: FastAPI):
    """设置API路由"""

    @app.post("/scan_folder")
    def scan_folder_api(req: ScanFolderRequest):
        """扫描文件夹中的帧图像"""
        try:
            frames = scan_folder_for_frames(req.folder_path)
            return {
                "success": True,
                "folder_path": req.folder_path,
                "frame_count": len(frames),
                "frames": frames,
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"扫描文件夹失败: {str(e)}")

    @app.get("/frame_image")
    def get_frame_image(folder_path: str = Query(...), filename: str = Query(...)):
        """返回指定帧图像内容"""
        if not os.path.isabs(folder_path):
            raise HTTPException(
                status_code=400, detail="不支持相对路径，只能用绝对路径"
            )

        file_path = os.path.join(folder_path, filename)
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail=f"图像文件不存在: {file_path}")

        valid_extensions = (".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif")
        if not file_path.lower().endswith(valid_extensions):
            raise HTTPException(status_code=400, detail="不支持的文件格式")

        return FileResponse(file_path, media_type="image/jpeg")

    @app.post("/segment_frame")
    def segment_frame_api(req: SegmentRequest):
        """提交单帧分割任务"""
        return enqueue_task(req)

    @app.post("/segment_frames")
    def segment_frames_api(req: SegmentBatchRequest):
        """提交多帧分割任务"""
        return enqueue_task(req)

    @app.post("/analyze_video", response_model=VideoAnalysisResponse)
    def analyze_video_api(req: VideoAnalysisRequest):
        """提交视频分析任务"""
        result = enqueue_task(req)
        return VideoAnalysisResponse(task_id=result["task_id"], status=result["status"])

    @app.post("/analyze_image", response_model=VisionAnalysisResponse)
    def analyze_image_api(req: VisionAnalysisRequest):
        """提交视频分析任务"""
        result = enqueue_task(req)
        return VisionAnalysisResponse(
            task_id=result["task_id"], status=result["status"]
        )

    @app.get("/task_status/{task_id}")
    def task_status_api(task_id: str):
        """查询任务状态"""
        return get_task_status(task_id)
