import ast
import json
import re
from io import BytesIO
from typing import Any, Dict, List

import numpy as np
import requests
from PIL import Image, ImageDraw, ImageFont


def parse_json_from_response(response: str) -> List[Dict[str, Any]]:
    """增强的JSON解析函数，兼容markdown和多种JSON格式"""

    try:
        import markdown
        from bs4 import BeautifulSoup

        html = markdown.markdown(response, extensions=["fenced_code"])
        soup = BeautifulSoup(html, "html.parser")
        code_block = soup.find("code")
        if code_block:
            json_text = code_block.text
            obj = json.loads(json_text)
            return obj
    except:
        pass

    if response.startswith("```json\n"):
        try:

            json_content = response[8:]
            if json_content.endswith("```"):
                json_content = json_content[:-3]

            last_valid_brace = json_content.rfind("}")
            if last_valid_brace != -1:

                repaired_json = json_content[: last_valid_brace + 1] + "]"

                obj = json.loads(repaired_json)
                return obj
        except Exception as e:
            print(f"修复JSON失败: {e}")

    try:
        return ast.literal_eval(response)
    except:

        end_idx = response.rfind('"}') + len('"}')
        truncated_text = response[:end_idx] + "]"
        return ast.literal_eval(truncated_text)


def draw_bounding_boxes(
    image: Image.Image, results: List[Dict], font_path: str = None
) -> Image.Image:
    """
    在图像上绘制边界框和标签（增强版）

    Args:
        image: PIL图像对象
        results: 检测结果列表
        font_path: 字体文件路径
    """
    (width, height) = image.size
    draw = ImageDraw.Draw(image)

    colors = [
        "red",
        "green",
        "blue",
        "yellow",
        "orange",
        "pink",
        "purple",
        "brown",
        "beige",
        "turquoise",
        "cyan",
        "magenta",
        "lime",
        "navy",
        "maroon",
        "teal",
        "olive",
        "coral",
        "lavender",
        "violet",
        "gold",
    ]

    font = load_font(font_path)

    for i, result in enumerate(results):
        color = colors[i % len(colors)]
        print(i, result)

        bbox = result.get("bbox_2d", [])
        if len(bbox) != 4:
            continue

        abs_coords = normalize_to_absolute_coords(bbox, width, height)
        [abs_x1, abs_y1, abs_x2, abs_y2] = abs_coords

        draw.rectangle([abs_x1, abs_y1, abs_x2, abs_y2], outline=color, width=3)

        label_text = build_label_text(result, i)

        draw_text_with_background(draw, abs_x1, abs_y1, label_text, color, font)

    return image


def load_font(font_path: str = None, default_size: int = 40):
    """加载字体，支持fallback"""
    font_paths = [
        font_path,
        "LXGWWenKaiGB-Regular.ttf",
        "NotoSansCJK-Regular.ttc",
        "Arial.ttf",
    ]

    for path in font_paths:
        if path:
            try:
                return ImageFont.truetype(path, default_size)
            except:
                continue
    return ImageFont.load_default()


def build_label_text(result: Dict, index: int) -> str:
    """构建标签文本"""
    label_parts = []
    if "label" in result:
        label_parts.append(result["label"])
    if "type" in result:
        label_parts.append(result["type"])
    if "color" in result:
        label_parts.append(result["color"])

    return " ".join(label_parts) if label_parts else f"obj_{index+1}"


def draw_text_with_background(
    draw: ImageDraw, x: int, y: int, text: str, color: str, font
):
    """绘制带背景的文本"""
    text_bbox = draw.textbbox((x, y), text, font=font)
    text_width = text_bbox[2] - text_bbox[0]
    text_height = text_bbox[3] - text_bbox[1]

    draw.rectangle([x, y - text_height - 15, x + text_width + 15, y], fill=color)

    draw.text((x, y - text_height - 20), text, fill="black", font=font)


def normalize_to_absolute_coords(
    bbox: List[float], width: int, height: int
) -> List[int]:
    """将归一化坐标转换为绝对坐标"""
    [x1, y1, x2, y2] = bbox
    abs_x1 = int(x1 / 1000 * width)
    abs_y1 = int(y1 / 1000 * height)
    abs_x2 = int(x2 / 1000 * width)
    abs_y2 = int(y2 / 1000 * height)

    if abs_x1 > abs_x2:
        abs_x1, abs_x2 = abs_x2, abs_x1
    if abs_y1 > abs_y2:
        abs_y1, abs_y2 = abs_y2, abs_y1

    return [abs_x1, abs_y1, abs_x2, abs_y2]


def load_image_from_source(image_source: str) -> Image.Image:
    """从文件路径或URL加载图像"""
    if image_source.startswith(("http://", "https://")):
        response = requests.get(image_source)
        response.raise_for_status()
        return Image.open(BytesIO(response.content))
    elif image_source.startswith("file://"):
        return Image.open(image_source[7:])
    else:
        return Image.open(image_source)
