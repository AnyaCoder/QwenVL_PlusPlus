import base64
from io import BytesIO

import numpy as np
from PIL import Image


def overlay_mask(
    frame: np.ndarray,
    mask: np.ndarray,
    obj_id=None,
    alpha: float = 0.4,
    use_random_color=False,
) -> np.ndarray:
    """改进的掩码覆盖函数"""
    mask = mask.squeeze()
    assert len(mask.shape) == 2, "Mask should be 2D (H, W)"

    def get_color(obj_id, use_random_color):
        if use_random_color:
            if obj_id is not None:
                np.random.seed(obj_id % 1000)
            return np.random.random(3)
        else:
            extended_colors = [
                [1.0, 0.0, 0.0],
                [0.0, 1.0, 0.0],
                [0.0, 0.0, 1.0],
                [1.0, 1.0, 0.0],
                [1.0, 0.0, 1.0],
                [0.0, 1.0, 1.0],
                [1.0, 0.5, 0.0],
                [0.5, 0.0, 1.0],
                [0.0, 0.5, 1.0],
                [1.0, 0.0, 0.5],
                [0.5, 1.0, 0.0],
                [0.0, 1.0, 0.5],
            ]
            if obj_id is None:
                return np.array(extended_colors[0])
            else:
                color_idx = obj_id % len(extended_colors)
                return np.array(extended_colors[color_idx])

    color = get_color(obj_id, use_random_color)
    frame = frame.astype(np.uint8)
    out = frame.copy()
    mask_bool = mask > 0

    for c in range(3):
        out_channel = out[:, :, c].astype(np.float32)
        out_channel[mask_bool] = (
            out_channel[mask_bool] * (1 - alpha) + color[c] * 255 * alpha
        )
        out[:, :, c] = np.clip(out_channel, 0, 255).astype(np.uint8)

    return out


def encode_image_to_base64(img_array: np.ndarray) -> str:
    """将numpy图像转换为base64编码的JPEG字符串"""
    buf = BytesIO()
    Image.fromarray(img_array).save(buf, format="JPEG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")
