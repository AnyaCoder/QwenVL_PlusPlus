from typing import Any, Dict, List, Optional

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
    user_prompt: str
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


class VisionAnalysisRequest(BaseModel):
    """视觉分析请求参数"""

    base64_images: list[str] = Field(..., description="Base64编码的图像数据")
    user_prompt: str = Field(..., description="用户提示词")

    class Config:
        json_schema_extra = {
            "example": {
                "base64_image": "base64_encoded_string_here",
                "user_prompt": "请分析这张图像中的物体并标注边界框",
            }
        }


class VisionAnalysisResponse(BaseModel):
    """视觉分析响应结果"""

    task_id: str
    status: str = Field(..., description="处理状态: success/error")
    results: Optional[List[Dict[str, Any]]] = Field(None, description="分析结果列表")
    annotated_image: Optional[str] = Field(None, description="带标注的Base64图像")
    detection_count: Optional[int] = Field(None, description="检测到的物体数量")
    error: Optional[str] = Field(None, description="错误信息")

    class Config:
        json_schema_extra = {
            "example": {
                "status": "success",
                "results": [
                    {
                        "label": "person",
                        "confidence": 0.95,
                        "bbox": [100, 150, 200, 300],
                    }
                ],
                "annotated_image": "base64_encoded_annotated_image",
                "detection_count": 1,
                "error": None,
            }
        }
