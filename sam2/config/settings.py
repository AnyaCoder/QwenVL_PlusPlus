from pathlib import Path

import torch
from pydantic import BaseModel


class Settings(BaseModel):
    # 模型配置
    model_cfg: str = "configs/sam2.1/sam2.1_hiera_l.yaml"
    ckpt_path: str = "../checkpoints/sam2.1_hiera_large.pt"
    qwen_model_path: str = (
        Path("~").expanduser()
        / ".cache/huggingface/hub/models--Qwen--Qwen3-VL-8B-Instruct/snapshots/0c351dd01ed87e9c1b53cbc748cba10e6187ff3b/"
    )
    # 设备配置
    llm_device: str = "cuda" if torch.cuda.is_available() else "cpu"
    video_device: str = "cuda:6" if torch.cuda.is_available() else "cpu"
    image_device: str = "cuda:7" if torch.cuda.is_available() else "cpu"

    # VLLM 初始化参数
    tensor_parallel_size: int = 4
    mm_encoder_tp_mode: str = "weights"

    # Qwen-VL 推理参数
    max_model_len: int = 16384
    llm_seed: int = 3407
    temperature: float = 0.7
    top_p: float = 0.8
    top_k: int = 20
    repetition_penalty: float = 1.0
    presence_penalty: float = 1.5
    max_new_tokens: int = 2048

    # 队列配置
    max_queue_wait_time: int = 30
    task_queue_maxsize: int = 5

    class Config:
        env_file = ".env"


settings = Settings()
