from typing import List, Optional

from pydantic import BaseModel, Field


class SegmentRequest(BaseModel):
    video_path: str
    filename: str
    frame_idx: int
    obj_ids: List[int]
    bboxes: List[List[float]]
    conf_threshold: float = 0.0


class SegmentBatchRequest(BaseModel):
    video_path: str
    filename: str
    frame_indices: List[int]
    obj_ids_list: List[List[int]]
    bboxes_list: List[List[List[float]]]
    conf_threshold: float = 0.0


class ScanFolderRequest(BaseModel):
    folder_path: str


class VideoAnalysisRequest(BaseModel):
    video_dir: str
    user_query: str
    original_fps: float = Field(default=12.5, ge=1.0, le=60.0)
    target_fps: float = Field(default=2.0, ge=0.1, le=30.0)
    frames_needed: int = Field(default=60, ge=1, le=200)
    grid_size: int = Field(default=16, ge=1, le=64)
    columns: int = Field(default=4, ge=1, le=8)


class VideoAnalysisResponse(BaseModel):
    task_id: str
    status: str
    grid_images: Optional[List[str]] = None
    results: Optional[List[dict]] = None
    error: Optional[str] = None
