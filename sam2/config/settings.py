import torch

# 模型配置
MODEL_CFG = "configs/sam2.1/sam2.1_hiera_l.yaml"
CKPT_PATH = "../checkpoints/sam2.1_hiera_large.pt"

# 设备配置
VIDEO_DEVICE = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
IMAGE_DEVICE = torch.device("cuda:1" if torch.cuda.is_available() else "cpu")

# 队列配置
MAX_QUEUE_WAIT_TIME = 30
TASK_QUEUE_MAXSIZE = 5
