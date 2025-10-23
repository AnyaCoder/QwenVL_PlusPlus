import os
import time
import torch
import numpy as np
from PIL import Image
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from pydantic import BaseModel
from queue import Queue, Empty
from threading import Thread
import subprocess
from copy import deepcopy
from sam2.build_sam import build_sam2, build_sam2_video_predictor
from sam2.sam2_image_predictor import SAM2ImagePredictor
from loguru import logger
import matplotlib.pyplot as plt
import glob
import base64
from io import BytesIO

# ---------------------- Task Queue Management ----------------------
import uuid
TASK_STATUS = {}  # task_id -> {"status": queued|processing|done|error, "result": ..., "frames": {...}}

# ---------------------- Configuration ----------------------
MAX_QUEUE_WAIT_TIME = 30  # seconds
TASK_QUEUE = Queue(maxsize=5)  # queue capacity
VIDEO_DEVICE = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
IMAGE_DEVICE = torch.device("cuda:1" if torch.cuda.is_available() else "cpu")
# Preload model once
MODEL_CFG = "configs/sam2.1/sam2.1_hiera_l.yaml"
CKPT_PATH = "../checkpoints/sam2.1_hiera_large.pt"
ML_MODELS = {}

# ---------------------- FastAPI Setup ----------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    ML_MODELS["video_predictor"] = build_sam2_video_predictor(MODEL_CFG, CKPT_PATH, device=VIDEO_DEVICE)
    sam2_model = build_sam2(MODEL_CFG, CKPT_PATH, device=IMAGE_DEVICE)
    ML_MODELS["image_predictor"] = SAM2ImagePredictor(sam2_model)
    Thread(target=worker_loop, daemon=True).start()
    logger.info("SAM2 models loaded (both video and image) and worker started.")
    yield
    ML_MODELS.clear()
    torch.cuda.empty_cache()


app = FastAPI(
    lifespan=lifespan,
    title="SAM2 Video Segmentation Service",
    description="Asynchronous queue-based video segmentation API using SAM2 + Decord for fast frame access."
)

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------- Request Schemas ----------------------
class SegmentRequest(BaseModel):
    video_path: str
    filename: str
    frame_idx: int
    obj_id: int
    bbox: list[float]
    conf_threshold: float = 0.0

class SegmentBatchRequest(BaseModel):
    video_path: str
    filename: str
    frame_indices: list[int]
    obj_ids: list[int]
    bboxes: list[list[float]]
    conf_threshold: float = 0.0

class ScanFolderRequest(BaseModel):
    folder_path: str

# ---------------------- Helper Functions ----------------------
def overlay_mask(frame: np.ndarray, mask: np.ndarray, obj_id=None, alpha: float = 0.4, use_random_color=False) -> np.ndarray:
    """改进的掩码覆盖函数，提供更丰富的颜色选择"""
    mask = mask.squeeze()  # (1, H, W) -> (H, W)
    assert len(mask.shape) == 2, "Mask should be 2D (H, W)"

    def get_color(obj_id, use_random_color):
        if use_random_color:
            if obj_id is not None:
                np.random.seed(obj_id % 1000)  # 限制种子范围
            return np.random.random(3)
        else:
            extended_colors = [
                [1.0, 0.0, 0.0],    # 红
                [0.0, 1.0, 0.0],    # 绿
                [0.0, 0.0, 1.0],    # 蓝
                [1.0, 1.0, 0.0],    # 黄
                [1.0, 0.0, 1.0],    # 紫
                [0.0, 1.0, 1.0],    # 青
                [1.0, 0.5, 0.0],    # 橙
                [0.5, 0.0, 1.0],    # 紫蓝
                [0.0, 0.5, 1.0],    # 天蓝
                [1.0, 0.0, 0.5],    # 粉红
                [0.5, 1.0, 0.0],    # 黄绿
                [0.0, 1.0, 0.5],    # 春绿
            ]
            if obj_id is None:
                return np.array(extended_colors[0])
            else:
                color_idx = obj_id % len(extended_colors)
                return np.array(extended_colors[color_idx])
    
    color = get_color(obj_id, use_random_color)
    out = frame.copy().astype(np.float32)
    colored_mask = np.zeros_like(out)
    mask_area = mask > 0
    for c in range(3):
        colored_mask[mask_area, c] = color[c] * 255
    # 更平滑的混合
    blend_mask = mask.astype(np.float32) * alpha
    blend_mask_3d = np.stack([blend_mask] * 3, axis=-1)
    out = out * (1 - blend_mask_3d) + colored_mask * blend_mask_3d
    return out.astype(np.uint8)

def extract_frames_from_video(video_path: str):
    """Use FFmpeg to extract frames from the provided video and save them as JPEG files."""
    # Create a folder for extracted frames
    video_dir = os.path.splitext(video_path)[0] + "_mp4"
    if not os.path.exists(video_dir):
        os.makedirs(video_dir)
    
    # Run FFmpeg to extract frames as JPEG
    cmd = f"ffmpeg -i {video_path} -q:v 2 -start_number 0 {video_dir}/%05d.jpg"
    subprocess.run(cmd, check=True, shell=True,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    return video_dir

def encode_image_to_base64(img_array: np.ndarray) -> str:
    """Convert numpy image to base64-encoded JPEG string."""
    buf = BytesIO()
    Image.fromarray(img_array).save(buf, format="JPEG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")

def scan_folder_for_frames(folder_path: str):
    if not os.path.exists(folder_path):
        raise HTTPException(status_code=404, detail=f"文件夹不存在: {folder_path}")
    
    image_extensions = ['*.jpg', '*.jpeg']
    frames = []
    
    for ext in image_extensions:
        pattern = os.path.join(folder_path, f"**/{ext}") if folder_path != "" else f"**/{ext}"
        files = glob.glob(pattern, recursive=True)
        
        for file_path in files:
            filename = os.path.basename(file_path)
            
            frames.append({
                "index": len(frames),
                "filename": filename,
                "file_path": file_path,
                "relative_path": os.path.relpath(file_path, folder_path) if folder_path != "" else file_path
            })
    
    frames.sort(key=lambda x: x["filename"])
    for i, frame in enumerate(frames):
        frame["index"] = i
    
    return frames

def extract_frame_index(filename: str) -> int:
    """从文件名中提取帧索引（此函数现在可能不需要了，但保留以备其他用途）"""
    # 由于现在按照文件名顺序排序，这个函数可能不再需要
    # 但为了兼容性保留
    name_without_ext = os.path.splitext(filename)[0]
    
    import re
    numbers = re.findall(r'\d+', name_without_ext)
    if numbers:
        return int(numbers[-1])
    
    return hash(filename) % 10000

# ---------------------- Core Segmentation Functions ---------------------
def segment_image(req: SegmentRequest):
    """Segment one image using SAM2 image predictor."""
    try:
        image_path = os.path.join(req.video_path, req.filename)
        if not os.path.exists(image_path):
            raise ValueError(f"Image file does not exist: {req.video_path}")
        
        image = Image.open(image_path)
        image = np.array(image.convert("RGB"))
        
        # Initialize image predictor
        ML_MODELS["image_predictor"].set_image(image)
        
        # Bounding box
        box = np.array(req.bbox, dtype=np.float32)
        
        # Predict mask
        masks, scores, _ = ML_MODELS["image_predictor"].predict(
            point_coords=None,
            point_labels=None,
            box=box[None, :],
            multimask_output=False,
        )
        
        # Get the best mask
        mask = masks[0].astype(np.float32)
        
        # Create overlay
        overlay = overlay_mask(image, mask, req.obj_id)
        
        return {str(req.frame_idx): encode_image_to_base64(overlay)}
        
    except Exception as e:
        logger.error(f"Image segmentation failed: {str(e)}")
        raise

def segment_images(req: SegmentBatchRequest):
    """Segment multiple images using SAM2 image predictor."""
    try:
        results = {}
        
        # Process each image
        for i, (frame_idx, obj_idx, bbox) in enumerate(zip(req.frame_indices, req.obj_ids, req.bboxes)):
            # For images, we use the same path for all (or could be adapted for multiple images)
            image_path = os.path.join(req.video_path, req.filename)
            if not os.path.exists(image_path):
                raise ValueError(f"Image file does not exist: {req.video_path}")
            
            image = Image.open(image_path)
            image = np.array(image.convert("RGB"))
            
            # Initialize image predictor for this image
            image_predictor = SAM2ImagePredictor(ML_MODELS["image_predictor"])
            image_predictor.set_image(image)
            
            # Bounding box
            box = np.array(bbox, dtype=np.float32)
            
            # Predict mask
            masks, scores, _ = image_predictor.predict(
                point_coords=None,
                point_labels=None,
                box=box[None, :],
                multimask_output=False,
            )
            
            # Get the best mask
            mask = masks[0].astype(np.float32)
            
            # Create overlay
            overlay = overlay_mask(image, mask, obj_idx)
            results[i] = encode_image_to_base64(overlay)
        
        return results
        
    except Exception as e:
        logger.error(f"Batch image segmentation failed: {str(e)}")
        raise

def segment_frame(req: SegmentRequest):
    """Segment one frame from the extracted JPEG frames."""
    # Check if the provided video is a .mp4 file
    video_path = req.video_path
    if video_path.endswith(".mp4"):
        # Extract frames if video is in mp4 format
        video_dir = extract_frames_from_video(video_path)
    else:
        # If the path is already a folder with extracted frames, use it directly
        video_dir = video_path
    
    # Read the frame as an image file
    frame_path = os.path.join(video_dir, req.filename)
    logger.info(f"frame_path: {frame_path}")
    if not os.path.exists(frame_path):
        raise ValueError(f"Frame {req.frame_idx} does not exist in {video_dir}.")
    
    frame = np.array(Image.open(frame_path))
    # Initialize the inference state using the frames folder
    inference_state = ML_MODELS["predictor"].init_state(video_path=video_dir)
    ML_MODELS["predictor"].reset_state(inference_state)

    # Bounding box
    box = np.array(req.bbox, dtype=np.float32)
    _, _, out_mask_logits = ML_MODELS["predictor"].add_new_points_or_box(
        inference_state=inference_state,
        frame_idx=req.frame_idx,
        obj_id=req.obj_id,
        box=box,
    )

    mask = (out_mask_logits[0].cpu().numpy() > req.conf_threshold).astype(np.float32)
    overlay = overlay_mask(frame, mask, req.obj_id)
    
    return {str(req.frame_idx): encode_image_to_base64(overlay)}

def segment_frames(req: SegmentBatchRequest):
    """Segment multiple frames from the extracted JPEG frames."""
    # Check if the provided video is a .mp4 file
    video_path = req.video_path
    if video_path.endswith(".mp4"):
        # Extract frames if video is in mp4 format
        video_dir = extract_frames_from_video(video_path)
    else:
        # If the path is already a folder with extracted frames, use it directly
        video_dir = video_path
    
    # Initialize the inference state using the frames folder
    inference_state = ML_MODELS["predictor"].init_state(video_path=video_dir)
    ML_MODELS["predictor"].reset_state(inference_state)
    
    results = {}
    
    # Process each frame
    for i, (frame_idx, obj_idx, bbox) in enumerate(zip(req.frame_indices, req.obj_ids, req.bboxes)):
        frame_path = os.path.join(video_dir, f"{i:05d}.jpg")
        if not os.path.exists(frame_path):
            raise ValueError(f"Frame {i} does not exist in {video_dir}.")
        
        frame = np.array(Image.open(frame_path))
        
        # Bounding box
        box = np.array(bbox, dtype=np.float32)
        _, _, out_mask_logits = ML_MODELS["predictor"].add_new_points_or_box(
            inference_state=inference_state,
            frame_idx=frame_idx,
            obj_id=obj_idx,
            box=box,
        )
        mask = (out_mask_logits[0].cpu().numpy() > req.conf_threshold).astype(np.float32)
        overlay = overlay_mask(frame, mask, obj_idx)
        results[i] = encode_image_to_base64(overlay)
    
    return results

# ---------------------- HTTP Endpoints ----------------------
@app.post("/scan_folder")
def scan_folder_api(req: ScanFolderRequest):
    """扫描文件夹中的帧图像"""
    try:
        frames = scan_folder_for_frames(req.folder_path)
        return {
            "success": True,
            "folder_path": req.folder_path,
            "frame_count": len(frames),
            "frames": frames
        }
    except Exception as e:
        logger.error(f"扫描文件夹失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"扫描文件夹失败: {str(e)}")


@app.get("/frame_image")
def get_frame_image(folder_path: str = Query(...), filename: str = Query(...)):
    """
    返回指定帧图像内容
    """
    # 支持相对路径和绝对路径
    if folder_path.startswith("../") or not os.path.isabs(folder_path):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        folder_path = os.path.abspath(os.path.join(base_dir, folder_path))

    file_path = os.path.join(folder_path, filename)

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail=f"图像文件不存在: {file_path}")

    # 可选：检查扩展名
    valid_extensions = ('.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif')
    if not file_path.lower().endswith(valid_extensions):
        raise HTTPException(status_code=400, detail="不支持的文件格式")

    # 直接返回文件流
    return FileResponse(file_path, media_type="image/jpeg")


@app.post("/segment_frame")
def segment_frame_api(req: SegmentRequest):
    """Submit single-frame segmentation task with optional saving."""
    return enqueue_task(req)

@app.post("/segment_frames")
def segment_frames_api(req: SegmentBatchRequest):
    """Submit multi-frame segmentation task with optional saving."""
    return enqueue_task(req)

def enqueue_task(req):
    """Put a task into the queue and return task_id immediately."""
    if TASK_QUEUE.full():
        raise HTTPException(status_code=429, detail="Queue is full, try again later.")

    task_id = str(uuid.uuid4())  # unique task id
    TASK_STATUS[task_id] = {"status": "queued", "result": None, "frames": {}}

    response_queue = Queue()
    TASK_QUEUE.put((task_id, req, response_queue))

    return {"status": "queued", "task_id": task_id}


def worker_loop():
    """Worker thread executes queued tasks sequentially and updates TASK_STATUS."""
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
                    if req.filename.endswith(('.jpg', '.jpeg')):
                        result = segment_image(req)
                    else:
                        result = segment_frame(req)
                    TASK_STATUS[task_id]["frames"][req.frame_idx] = "done"
                elif isinstance(req, SegmentBatchRequest):
                    if req.filename.endswith(('.jpg', '.jpeg')):
                        results = segment_images(req)
                    else:
                        results = segment_frames(req)
                    for idx, img_b64 in results.items():
                        TASK_STATUS[task_id]["frames"][idx] = "done"
                    result = results
                else:
                    raise ValueError(f"Unknown request type: {type(req)}")
                
                TASK_STATUS[task_id]["status"] = "done"
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

@app.get("/task_status/{task_id}")
def task_status(task_id: str):
    """Query task status."""
    if task_id not in TASK_STATUS:
        raise HTTPException(status_code=404, detail="Task ID not found")
    
    task_info = TASK_STATUS[task_id]
    # If the task is done or error, return the result/error message
    if task_info["status"] in ["done", "error"]:
        r_info = deepcopy(task_info)
        del task_info
        return r_info
    
    # Otherwise, it's queued or processing, show status
    return {"status": task_info["status"], "task_id": task_id}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)