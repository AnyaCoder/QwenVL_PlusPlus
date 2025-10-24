import os

import numpy as np
from loguru import logger
from PIL import Image

from models.schemas import SegmentBatchRequest, SegmentRequest
from services.model_service import model_service
from utils.image_utils import encode_image_to_base64, overlay_mask
from utils.video_utils import extract_frames_from_video


class SegmentationService:
    def segment_image(self, req: SegmentRequest):
        """单图像多框分割"""
        try:
            image_path = os.path.join(req.video_path, req.filename)
            if not os.path.exists(image_path):
                raise ValueError(f"Image file does not exist: {image_path}")

            image = Image.open(image_path)
            image = np.array(image.convert("RGB"))

            image_predictor = model_service.get_model("image_predictor")
            image_predictor.set_image(image)

            input_boxes = np.array(req.bboxes, dtype=np.float32)
            masks, scores, _ = image_predictor.predict(
                point_coords=None,
                point_labels=None,
                box=input_boxes,
                multimask_output=False,
            )

            masks = masks.squeeze(1)
            mask_data = list(zip(req.obj_ids, masks))
            mask_data.sort(key=lambda x: x[0])

            combined_overlay = image.copy()
            for obj_id, mask in mask_data:
                combined_overlay = overlay_mask(combined_overlay, mask, obj_id)

            return {str(req.frame_idx): encode_image_to_base64(combined_overlay)}

        except Exception as e:
            logger.error(f"Multi-box image segmentation failed: {str(e)}")
            raise

    def segment_images(self, req: SegmentBatchRequest):
        """批量图像分割"""
        try:
            results = {}
            for i, (frame_idx, obj_ids, bboxes) in enumerate(
                zip(req.frame_indices, req.obj_ids_list, req.bboxes_list)
            ):
                image_path = os.path.join(req.video_path, req.filename)
                if not os.path.exists(image_path):
                    raise ValueError(f"Image file does not exist: {req.video_path}")

                image = Image.open(image_path)
                image = np.array(image.convert("RGB"))

                image_predictor = model_service.get_model("image_predictor")
                image_predictor.set_image(image)

                input_boxes = np.array(bboxes, dtype=np.float32)
                masks, scores, _ = image_predictor.predict(
                    point_coords=None,
                    point_labels=None,
                    box=input_boxes,
                    multimask_output=False,
                )

                masks = masks.squeeze(1)
                mask_data = list(zip(obj_ids, masks))
                mask_data.sort(key=lambda x: x[0])

                combined_overlay = image.copy()
                for obj_id, mask in mask_data:
                    combined_overlay = overlay_mask(combined_overlay, mask, obj_id)

                results[i] = encode_image_to_base64(combined_overlay)

            return results

        except Exception as e:
            logger.error(f"Batch image segmentation failed: {str(e)}")
            raise


# 全局分割服务实例
segmentation_service = SegmentationService()
