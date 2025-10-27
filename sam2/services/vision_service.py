# services/vision_analysis_service.py
import math
import os
import re
from typing import Any, Dict, List

import natsort
import numpy as np
from loguru import logger
from models.schemas import VisionAnalysisRequest
from services.model_service import model_service
from utils.image_utils import decode_base64_to_image, encode_image_to_base64
from utils.vision_utils import draw_bounding_boxes, parse_json_from_response


class VisionAnalysisService:

    def generate_image_content(
        self, folder_path: str, orig_fps: float, target_fps: float, total_frames: int
    ) -> List[Dict]:
        """从视频帧文件夹中按目标帧率采样图像并生成带时间戳的消息列表"""
        folder_path = os.path.abspath(folder_path)

        jpg_files = [f for f in os.listdir(folder_path) if f.lower().endswith(".jpg")]
        jpg_files = natsort.natsorted(jpg_files)
        total_available = len(jpg_files)

        if total_available == 0:
            raise ValueError(f"在文件夹 {folder_path} 中未找到.jpg文件")

        if total_frames > total_available:
            logger.warning(
                f"所需帧数({total_frames})超过实际({total_available})，已调整为{total_available}"
            )
            total_frames = total_available

        if target_fps > orig_fps:
            raise ValueError(f"目标帧率({target_fps})不能大于原始帧率({orig_fps})")

        if total_frames == 1:
            selected_indices = [0]
        else:
            step = (total_available - 1) // (total_frames - 1)
            selected_indices = [i * step for i in range(total_frames)]
            selected_indices = [
                min(idx, total_available - 1) for idx in selected_indices
            ]

        image_paths = [
            os.path.join(folder_path, jpg_files[i]) for i in selected_indices
        ]
        seconds = [i / orig_fps for i in selected_indices]

        message_content = []
        for sec, img_path in zip(seconds, image_paths):
            message_content.append({"type": "text", "text": f"<{sec:.2f} seconds>"})
            message_content.append(
                {
                    "type": "image",
                    "image": f"file://{img_path}",
                    "resized_width": 640,
                    "resized_height": 360,
                }
            )

        return message_content

    def get_messages_with_images(
        self,
        video_dir: str,
        user_prompt: str,
        original_fps: float = 12.5,
        target_fps: float = 2,
        frames_needed: int = 100,
    ) -> List[Dict]:
        """构建包含视频帧和用户提示的完整消息"""
        images_content = self.generate_image_content(
            video_dir, original_fps, target_fps, frames_needed
        )

        messages = [
            {
                "role": "user",
                "content": [*images_content, {"type": "text", "text": user_prompt}],
            }
        ]

        return messages

    def analyze_image(self, req: VisionAnalysisRequest) -> Dict[str, Any]:
        """分析单张图像并返回带标注的结果"""

        images_content = []

        for i, base64_image in enumerate(req.base64_images):
            image = decode_base64_to_image(base64_image)

            image_url = f"data:image/jpeg;base64,{base64_image}"

            images_content.extend(
                [
                    {"type": "text", "text": f"<{i+1} seconds>"},
                    {
                        "type": "image_url",
                        "image_url": image_url,
                        "resized_width": 640,
                        "resized_height": 360,
                    },
                ]
            )

        messages = [
            {
                "role": "user",
                "content": [
                    *images_content,
                    {"type": "text", "text": req.user_prompt},
                ],
            }
        ]

        response = model_service.inference(messages)
        results = parse_json_from_response(response)
        annotated_image = draw_bounding_boxes(image.copy(), results)
        annotated_base64 = encode_image_to_base64(np.array(annotated_image))

        return {
            "status": "success",
            "results": results,
            "annotated_image": annotated_base64,
            "detection_count": len(results),
        }


vision_service = VisionAnalysisService()
