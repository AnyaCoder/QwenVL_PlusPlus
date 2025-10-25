import json
import math
import os
import re
from io import BytesIO
from typing import Any, Dict, List

import markdown
import natsort
import numpy as np
import requests
from bs4 import BeautifulSoup
from loguru import logger
from PIL import Image, ImageDraw, ImageFont
from vllm import SamplingParams

from config.settings import settings
from models.schemas import VideoAnalysisRequest
from services.model_service import model_service
from utils.image_utils import encode_image_to_base64


class VisionAnalysisService:
    def draw_bbox(self, image: Image.Image, bbox: List[float]) -> Image.Image:
        """在图像上绘制边界框"""
        draw = ImageDraw.Draw(image)
        draw.rectangle(bbox, outline="red", width=4)
        return image

    def create_image_grid_pil(
        self, pil_images: List[Image.Image], num_columns: int = 4
    ) -> Image.Image:
        """创建图像网格"""
        if not pil_images:
            return None

        num_rows = math.ceil(len(pil_images) / num_columns)
        img_width, img_height = pil_images[0].size

        grid_width = num_columns * img_width
        grid_height = num_rows * img_height
        grid_image = Image.new("RGB", (grid_width, grid_height), color="white")

        for idx, image in enumerate(pil_images):
            row_idx = idx // num_columns
            col_idx = idx % num_columns
            position = (col_idx * img_width, row_idx * img_height)
            grid_image.paste(image, position)

        return grid_image

    def parse_json(self, response: str) -> List[Dict[str, Any]]:
        """解析模型响应中的JSON数据"""
        html = markdown.markdown(response, extensions=["fenced_code"])
        soup = BeautifulSoup(html, "html.parser")
        code_block = soup.find("code")

        if not code_block:
            raise ValueError("No JSON code block found in response")

        json_text = code_block.text
        data = json.loads(json_text)
        return data

    def create_timestamped_image(
        self, image: Image.Image, time_str: str
    ) -> Image.Image:
        """在图像上添加时间戳文本"""
        draw = ImageDraw.Draw(image)
        font = ImageFont.truetype("LXGWWenKaiGB-Regular.ttf", 40)
        draw.text(
            (10, 10),
            f"Time: {time_str}s",
            fill="red",
            stroke_width=20,
            stroke_fill="white",
        )
        return image

    def get_image_by_timestamp(
        self, messages: List[Dict], timestamp: float
    ) -> Image.Image:
        """根据时间戳从消息中获取对应的图像"""
        pattern = r"<(\d+\.\d+) seconds>"
        contents = messages[0]["content"]
        for content_idx, content in enumerate(contents):
            if content["type"] == "text" and "seconds>" in content["text"]:
                match = re.search(pattern, content["text"])
                image_sec = float(match.group(1))
                if content_idx + 1 < len(contents) and image_sec >= timestamp:
                    next_content = contents[content_idx + 1]
                    if next_content["type"] == "image":
                        image_url = next_content["image"]
                        if image_url.startswith("file://"):
                            image_path = image_url[7:]
                            return Image.open(image_path)
                        else:
                            return Image.open(BytesIO(requests.get(image_url).content))
        return None

    def process_single_result(self, result: Dict, messages: List[Dict]) -> Image.Image:
        """处理单个检测结果，返回带边界框的图像"""
        image = self.get_image_by_timestamp(messages, result["time"])
        if image is None:
            return None

        image_width, image_height = image.size
        x_min, y_min, x_max, y_max = result["bbox_2d"]

        x_min = x_min / 1000 * image_width
        y_min = y_min / 1000 * image_height
        x_max = x_max / 1000 * image_width
        y_max = y_max / 1000 * image_height

        image_with_bbox = self.draw_bbox(image.copy(), [x_min, y_min, x_max, y_max])
        image_with_timestamp = self.create_timestamped_image(
            image_with_bbox, str(result["time"])
        )

        return image_with_timestamp

    def generate_all_grids_base64(
        self,
        results: List[Dict],
        messages: List[Dict],
        grid_size: int = 16,
        columns: int = 4,
    ) -> List[str]:
        """为所有结果生成多个网格图像，返回base64编码列表"""
        if not results:
            logger.info("没有检测结果可处理")
            return []

        total_results = len(results)
        num_grids = math.ceil(total_results / grid_size)
        logger.info(
            f"共有 {total_results} 个检测结果，需要生成 {num_grids} 个 {columns}×{columns} 网格"
        )

        grid_images_base64 = []

        for grid_idx in range(num_grids):
            start_idx = grid_idx * grid_size
            end_idx = min((grid_idx + 1) * grid_size, total_results)
            grid_results = results[start_idx:end_idx]

            logger.info(f"处理网格 {grid_idx + 1}: 结果 {start_idx + 1}-{end_idx}")

            grid_vis_images = []
            for i, result in enumerate(grid_results):
                processed_image = self.process_single_result(result, messages)
                if processed_image:
                    grid_vis_images.append(processed_image)

            if grid_vis_images:
                grid_image = self.create_image_grid_pil(
                    grid_vis_images, num_columns=columns
                )
                grid_base64 = encode_image_to_base64(np.array(grid_image))
                grid_images_base64.append(grid_base64)
                logger.info(f"网格 {grid_idx + 1} 处理完成")
            else:
                logger.warning(f"网格 {grid_idx + 1} 没有可处理的图像")

        return grid_images_base64

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

    def inference(self, messages: List[Dict]) -> str:
        """使用vLLM执行模型推理"""
        inputs = [model_service.prepare_qwen_inputs(messages)]

        sampling_params = SamplingParams(
            temperature=settings.temperature,
            max_tokens=settings.max_new_tokens,
            seed=settings.llm_seed,
            top_p=settings.top_p,
            top_k=settings.top_k,
            repetition_penalty=settings.repetition_penalty,
            presence_penalty=settings.presence_penalty,
            stop_token_ids=[],
        )
        llm = model_service.get_qwen_llm()
        outputs = llm.generate(inputs, sampling_params=sampling_params)
        return outputs[0].outputs[0].text

    def analyze_video(self, request: VideoAnalysisRequest) -> Dict[str, Any]:
        """执行视频分析的主函数"""
        try:

            messages = self.get_messages_with_images(
                request.video_dir,
                request.user_prompt,
                request.original_fps,
                request.target_fps,
                request.frames_needed,
            )
            logger.info(f"开始模型推理...")

            response = self.inference(messages)
            logger.info(f"模型推理完成, response:\n {response}")

            results = self.parse_json(response)
            logger.info(f"解析到 {len(results)} 个检测结果")
            grid_images = self.generate_all_grids_base64(
                results, messages, request.grid_size, request.columns
            )

            return {
                "status": "success",
                "results": results,
                "grid_images": grid_images,
                "grid_count": len(grid_images),
            }

        except Exception as e:
            logger.error(f"视频分析失败: {str(e)}")
            return {"status": "error", "error": str(e)}


vision_service = VisionAnalysisService()
