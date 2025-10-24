import glob
import os

from fastapi import HTTPException
from loguru import logger


def scan_folder_for_frames(folder_path: str):
    """扫描文件夹中的帧图像"""
    if not os.path.exists(folder_path):
        raise HTTPException(status_code=404, detail=f"文件夹不存在: {folder_path}")

    image_extensions = ["*.jpg", "*.jpeg"]
    frames = []

    for ext in image_extensions:
        pattern = (
            os.path.join(folder_path, f"**/{ext}") if folder_path != "" else f"**/{ext}"
        )
        files = glob.glob(pattern, recursive=True)

        for file_path in files:
            filename = os.path.basename(file_path)
            frames.append(
                {
                    "index": len(frames),
                    "filename": filename,
                    "file_path": file_path,
                    "relative_path": (
                        os.path.relpath(file_path, folder_path)
                        if folder_path != ""
                        else file_path
                    ),
                }
            )

    frames.sort(key=lambda x: x["filename"])
    for i, frame in enumerate(frames):
        frame["index"] = i

    return frames
