import torch
from loguru import logger

from config.settings import CKPT_PATH, IMAGE_DEVICE, MODEL_CFG, VIDEO_DEVICE
from sam2.build_sam import build_sam2, build_sam2_video_predictor
from sam2.sam2_image_predictor import SAM2ImagePredictor


class ModelService:
    def __init__(self):
        self.models = {}
        self._load_models()

    def _load_models(self):
        """加载视频和图像分割模型"""
        try:
            self.models["video_predictor"] = build_sam2_video_predictor(
                MODEL_CFG, CKPT_PATH, device=VIDEO_DEVICE
            )
            sam2_model = build_sam2(MODEL_CFG, CKPT_PATH, device=IMAGE_DEVICE)
            self.models["image_predictor"] = SAM2ImagePredictor(sam2_model)
            logger.info("SAM2 models loaded successfully (both video and image)")
        except Exception as e:
            logger.error(f"Failed to load models: {str(e)}")
            raise

    def get_model(self, model_type):
        """获取指定类型的模型"""
        return self.models.get(model_type)

    def cleanup(self):
        """清理模型资源"""
        self.models.clear()
        torch.cuda.empty_cache()
        logger.info("Models cleaned up")


# 全局模型服务实例
model_service = ModelService()
