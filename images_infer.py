import json
import math
import os
from io import BytesIO

import markdown
import natsort
import requests
import torch
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw
from qwen_vl_utils import process_vision_info
from transformers import AutoProcessor
from vllm import LLM, SamplingParams

os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["HF_DATASETS_OFFLINE"] = "1"
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
os.environ["VLLM_WORKER_MULTIPROC_METHOD"] = "spawn"


model_path = os.environ.get("MODEL_PATH")
processor = None
llm = None


def initialize_models():
    """初始化处理器和vLLM模型"""
    global processor, llm

    print(f"正在初始化模型: {model_path}")

    processor = AutoProcessor.from_pretrained(model_path)
    max_model_len = int(os.environ.get("max_model_len", 32768))
    llm_seed = int(os.environ.get("llm_seed", 42))
    llm = LLM(
        model=model_path,
        max_model_len=max_model_len,
        seed=llm_seed,
    )

    print("模型初始化完成")


def prepare_inputs_for_vllm(messages, processor):
    """准备vLLM推理所需的输入数据
`
    Args:
        messages: 消息列表
        processor: 处理器实例

    Returns:
        dict: 包含prompt、multi_modal_data和mm_processor_kwargs的字典
    """
    text = processor.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True
    )

    image_inputs, video_inputs, video_kwargs = process_vision_info(
        messages,
        image_patch_size=processor.image_processor.patch_size,
        return_video_kwargs=True,
        return_video_metadata=True,
    )

    mm_data = {}
    if image_inputs is not None:
        mm_data["image"] = image_inputs
    if video_inputs is not None:
        mm_data["video"] = video_inputs

    return {
        "prompt": text,
        "multi_modal_data": mm_data,
        "mm_processor_kwargs": video_kwargs,
    }


def draw_bbox(image, bbox):
    """在图像上绘制边界框"""
    draw = ImageDraw.Draw(image)
    draw.rectangle(bbox, outline="red", width=4)
    return image


def create_image_grid_pil(pil_images, num_columns=4, fill_empty=True):
    """创建图像网格，可选的空位填充"""
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


def parse_json(response):
    """解析模型响应中的JSON数据"""
    html = markdown.markdown(response, extensions=["fenced_code"])
    soup = BeautifulSoup(html, "html.parser")
    json_text = soup.find("code").text

    data = json.loads(json_text)
    return data


def create_timestamped_image(image, time_str):
    """在图像上添加时间戳文本"""
    draw = ImageDraw.Draw(image)
    draw.text(
        (10, 10), f"Time: {time_str}s", fill="red", stroke_width=2, stroke_fill="white"
    )
    return image


def get_image_by_timestamp(messages, timestamp):
    """根据时间戳从消息中获取对应的图像"""
    time_str = str(timestamp)

    for content_idx, content in enumerate(messages[0]["content"]):
        if content["type"] == "text" and time_str in content["text"]:

            if content_idx + 1 < len(messages[0]["content"]):
                next_content = messages[0]["content"][content_idx + 1]
                if next_content["type"] == "image":
                    image_url = next_content["image"]
                    if image_url.startswith("file://"):
                        image_path = image_url[7:]
                        return Image.open(image_path)
                    else:
                        return Image.open(BytesIO(requests.get(image_url).content))
    return None


def process_single_result(result, messages):
    """处理单个检测结果，返回带边界框的图像"""
    image = get_image_by_timestamp(messages, result["time"])
    if image is None:
        return None

    image_width, image_height = image.size
    x_min, y_min, x_max, y_max = result["bbox_2d"]
    x_min = x_min / 1000 * image_width
    y_min = y_min / 1000 * image_height
    x_max = x_max / 1000 * image_width
    y_max = y_max / 1000 * image_height

    image_with_bbox = draw_bbox(image.copy(), [x_min, y_min, x_max, y_max])
    image_with_timestamp = create_timestamped_image(
        image_with_bbox, str(result["time"])
    )

    return image_with_timestamp


def generate_all_grids(results, messages, output_dir=".", grid_size=16, columns=4):
    """为所有结果生成多个4×4网格图像"""
    if not results:
        print("没有检测结果可处理")
        return []

    total_results = len(results)
    num_grids = math.ceil(total_results / grid_size)

    print(
        f"共有 {total_results} 个检测结果，需要生成 {num_grids} 个 {columns}×{columns} 网格"
    )

    grid_images = []

    for grid_idx in range(num_grids):
        start_idx = grid_idx * grid_size
        end_idx = min((grid_idx + 1) * grid_size, total_results)
        grid_results = results[start_idx:end_idx]

        print(f"处理网格 {grid_idx + 1}: 结果 {start_idx + 1}-{end_idx}")

        grid_vis_images = []
        for result in grid_results:
            processed_image = process_single_result(result, messages)
            if processed_image:
                grid_vis_images.append(processed_image)

        if grid_vis_images:
            grid_image = create_image_grid_pil(grid_vis_images, num_columns=columns)

            output_path = os.path.join(
                output_dir, f"detection_grid_{grid_idx + 1}_{columns}x{columns}.jpg"
            )
            grid_image.save(output_path)
            grid_images.append(grid_image)

            print(f"网格 {grid_idx + 1} 已保存到: {output_path}")

            grid_output_dir = os.path.join(output_dir, f"grid_{grid_idx + 1}")
            os.makedirs(grid_output_dir, exist_ok=True)

            for i, img in enumerate(grid_vis_images):
                single_output_path = os.path.join(
                    grid_output_dir,
                    f"frame_{start_idx + i + 1}_time_{grid_results[i]['time']}.jpg",
                )
                img.save(single_output_path)

            print(f"已保存 {len(grid_vis_images)} 张单独图像到 {grid_output_dir}")
        else:
            print(f"网格 {grid_idx + 1} 没有可处理的图像")

    return grid_images


def generate_image_content(folder_path, orig_fps, target_fps, total_frames):
    """从视频帧文件夹中按目标帧率采样图像并生成带时间戳的消息列表"""
    folder_path = os.path.abspath(folder_path)

    jpg_files = [f for f in os.listdir(folder_path) if f.lower().endswith(".jpg")]
    jpg_files = natsort.natsorted(jpg_files)
    total_available = len(jpg_files)

    if total_available == 0:
        print("提示：未找到.jpg文件")
        return []

    if total_frames > total_available:
        print(
            f"提示：所需帧数({total_frames})超过实际({total_available})，已调整为{total_available}"
        )
        total_frames = total_available

    if target_fps > orig_fps:
        raise ValueError(f"目标帧率({target_fps})不能大于原始帧率({orig_fps})")

    if total_frames == 1:
        selected_indices = [0]
    else:
        step = (total_available - 1) // (total_frames - 1)
        selected_indices = [i * step for i in range(total_frames)]
        selected_indices = [min(idx, total_available - 1) for idx in selected_indices]

    image_path = [os.path.join(folder_path, jpg_files[i]) for i in selected_indices]
    seconds = [i / orig_fps for i in selected_indices]

    message = []
    for sec, img_path in zip(seconds, image_path):
        message.append({"type": "text", "text": f"<{sec:.2f} seconds>"})
        message.append(
            {
                "type": "image",
                "image": f"file://{img_path}",
                "resized_width": 640,
                "resized_height": 360,
            }
        )

    return message


def get_messages_with_images(
    video_dir: str, user_prompt: str, original_fps=12.5, target_fps=2, frames_needed=100
):
    """构建包含视频帧和用户提示的完整消息"""
    images_content = generate_image_content(
        video_dir, original_fps, target_fps, frames_needed
    )
    messages = [
        {
            "role": "user",
            "content": [*images_content, {"type": "text", "text": user_prompt}],
        }
    ]
    return messages


def inference(messages):
    """使用vLLM执行模型推理"""

    inputs = [prepare_inputs_for_vllm(messages, processor)]

    seed = int(os.environ.get("seed", 3407))
    top_p = float(os.environ.get("top_p", 0.8))
    top_k = int(os.environ.get("top_k", 20))
    temperature = float(os.environ.get("temperature", 0.7))
    repetition_penalty = float(os.environ.get("repetition_penalty", 1.0))
    presence_penalty = float(os.environ.get("presence_penalty", 1.5))
    max_new_tokens = int(os.environ.get("max_new_tokens", 4096))
    
    sampling_params = SamplingParams(
        temperature=temperature,
        max_tokens=max_new_tokens,
        seed=seed,
        top_p=top_p,
        top_k=top_k,
        repetition_penalty=repetition_penalty,
        presence_penalty=presence_penalty,
        stop_token_ids=[],
    )

    outputs = llm.generate(inputs, sampling_params=sampling_params)

    return outputs[0].outputs[0].text


def main():
    """主函数"""

    initialize_models()

    video_dir = "videos/s050_camera_basler_south_50mm"
    original_fps = 12.5
    target_fps = 2
    frames_needed = 60
    output_dir = "."
    grid_size = 16
    columns = 4

    query = "At first there is a white van stopped in the middle of the road. Track that van."
    user_prompt = str(
        f'Given the query "{query}", for each frame, '
        "detect and localize the visual content described by the given textual query in JSON format. "
        "If the visual content does not exist in a frame, skip that frame. bbox_2d and label sometimes varies over time. Output Format: "
        '[{"time": 1.0, "bbox_2d": [x_min, y_min, x_max, y_max], "label": ""}, {"time": 2.0, "bbox_2d": [x_min, y_min, x_max, y_max], "label": ""}, ...].'
    )

    image_messages = get_messages_with_images(
        video_dir, user_prompt, original_fps, target_fps, frames_needed
    )
    print("构建的消息结构:")
    print(json.dumps(image_messages, ensure_ascii=False, indent=2))

    response = inference(image_messages)
    print("模型响应:")
    print(response)

    try:
        results = parse_json(response)
        print(f"解析到 {len(results)} 个检测结果")

        grid_images = generate_all_grids(
            results, image_messages, output_dir, grid_size, columns
        )

        if grid_images:
            print(f"成功生成 {len(grid_images)} 个网格图像")

    except Exception as e:
        print(f"解析或可视化过程中出现错误: {e}")
        print("原始响应:")
        print(response)


if __name__ == "__main__":
    main()
