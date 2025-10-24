from pydantic import BaseModel


class SegmentRequest(BaseModel):
    video_path: str
    filename: str
    frame_idx: int
    obj_ids: list[int]
    bboxes: list[list[float]]
    conf_threshold: float = 0.0


class SegmentBatchRequest(BaseModel):
    video_path: str
    filename: str
    frame_indices: list[int]
    obj_ids_list: list[list[int]]
    bboxes_list: list[list[list[float]]]
    conf_threshold: float = 0.0


class ScanFolderRequest(BaseModel):
    folder_path: str
