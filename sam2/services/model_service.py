import torch
from config.settings import settings
from loguru import logger
from qwen_vl_utils import process_vision_info
from transformers import AutoProcessor
from vllm import LLM, SamplingParams

from sam2.build_sam import build_sam2, build_sam2_video_predictor
from sam2.sam2_image_predictor import SAM2ImagePredictor


class ModelService:
    def __init__(self):
        self.models = {}

    def _load_sam2_models(self):
        """加载SAM2视频和图像分割模型"""
        try:
            logger.info("正在加载SAM2模型...")
            self.models["video_predictor"] = build_sam2_video_predictor(
                settings.model_cfg, settings.ckpt_path, device=settings.video_device
            )
            sam2_model = build_sam2(
                settings.model_cfg, settings.ckpt_path, device=settings.image_device
            )
            self.models["image_predictor"] = SAM2ImagePredictor(sam2_model)
            logger.info("SAM2模型加载成功")
        except Exception as e:
            logger.error(f"SAM2模型加载失败: {str(e)}")
            raise

    def _load_qwen_vl_model(self):
        """加载Qwen-VL模型"""
        try:
            logger.info(f"正在加载Qwen-VL模型: {settings.qwen_model_path}")

            self.models["qwen_processor"] = AutoProcessor.from_pretrained(
                settings.qwen_model_path
            )

            self.models["qwen_llm"] = LLM(
                model=settings.qwen_model_path,
                max_model_len=settings.max_model_len,
                tensor_parallel_size=settings.tensor_parallel_size,
                mm_encoder_tp_mode=settings.mm_encoder_tp_mode,
                seed=settings.llm_seed,
            )

            logger.info("Qwen-VL模型加载成功")
        except Exception as e:
            logger.error(f"Qwen-VL模型加载失败: {str(e)}")
            raise

    def _load_models(self):
        """加载所有模型"""
        self._load_sam2_models()
        self._load_qwen_vl_model()

    def get_model(self, model_type):
        """获取指定类型的模型"""
        return self.models.get(model_type)

    def get_qwen_processor(self):
        """获取Qwen-VL处理器"""
        return self.models.get("qwen_processor")

    def get_qwen_llm(self):
        """获取Qwen-VL LLM实例"""
        return self.models.get("qwen_llm")

    def inference(self, messages) -> str:
        """准备Qwen-VL推理输入"""
        processor = self.get_qwen_processor()

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
        llm = self.get_qwen_llm()
        inputs = [
            {
                "prompt": text,
                "multi_modal_data": mm_data,
                "mm_processor_kwargs": video_kwargs,
            }
        ]
        outputs = llm.generate(inputs, sampling_params=sampling_params)
        return outputs[0].outputs[0].text

    def cleanup(self):
        """清理模型资源"""
        self.models.clear()
        torch.cuda.empty_cache()
        logger.info("所有模型资源已清理")


model_service = ModelService()
