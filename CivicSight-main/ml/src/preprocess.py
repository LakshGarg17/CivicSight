"""CivicSight ML Pipeline — Report Image Preprocessing Module (Week 4)

Provides consistent, reusable image preprocessing bridging raw citizen report uploads
on disk to normalized tensors expected by YOLO models during inference and feature extraction.

Standard operations:
- Image loading from file path, PIL Image, or NumPy array
- Aspect-ratio preserving letterbox resizing with constant neutral padding
- Channel alignment (BGR/RGBA -> RGB)
- Normalization (uint8 [0, 255] -> float32 [0.0, 1.0])
- Format transposition (HWC -> CHW -> NCHW [1, 3, 640, 640])
- Transformation metadata tracking for downstream bbox coordinate inversion
"""

from typing import Union, Tuple, Dict, Any
from pathlib import Path
import cv2
import numpy as np
import torch
from PIL import Image


def letterbox_image(
    image: np.ndarray,
    target_shape: Tuple[int, int] = (640, 640),
    fill_color: Tuple[int, int, int] = (114, 114, 114),
    auto_stride: int = 32,
    scaleup: bool = True,
) -> Tuple[np.ndarray, float, Tuple[float, float]]:
    """Resizes and pads image to target_shape while preserving aspect ratio.
    
    Args:
        image: Source image array in HWC format.
        target_shape: Desired (height, width), typically (640, 640).
        fill_color: Neutral gray border padding (default 114 for YOLO).
        auto_stride: Ensure dimensions are multiples of minimum stride (32).
        scaleup: If False, only scale down, never scale up.

    Returns:
        padded_image: Resized & padded image array.
        ratio: Scale ratio applied.
        (pad_w, pad_h): Padding offsets (pixels) added to each side.
    """
    orig_shape = image.shape[:2]  # [height, width]
    
    # Scale ratio (new / old)
    r = min(target_shape[0] / orig_shape[0], target_shape[1] / orig_shape[1])
    if not scaleup:
        r = min(r, 1.0)

    # Compute unpadded new dimensions
    new_unpad = (int(round(orig_shape[1] * r)), int(round(orig_shape[0] * r)))
    dw, dh = target_shape[1] - new_unpad[0], target_shape[0] - new_unpad[1]

    # Divide padding into 2 sides
    dw /= 2
    dh /= 2

    # Resize image
    if orig_shape[::-1] != new_unpad:
        image = cv2.resize(image, new_unpad, interpolation=cv2.INTER_LINEAR)

    top, bottom = int(round(dh - 0.1)), int(round(dh + 0.1))
    left, right = int(round(dw - 0.1)), int(round(dw + 0.1))

    # Add constant border
    padded_image = cv2.copyMakeBorder(
        image, top, bottom, left, right, cv2.BORDER_CONSTANT, value=fill_color
    )

    return padded_image, r, (dw, dh)


def preprocess_report_image(
    image_input: Union[str, Path, Image.Image, np.ndarray],
    target_size: Tuple[int, int] = (640, 640),
    device: str = "cpu",
) -> Dict[str, Any]:
    """Preprocesses an uploaded citizen road damage image for YOLO model consumption.

    Args:
        image_input: File path, PIL Image, or OpenCV NumPy array.
        target_size: Target (height, width) dimensions, default (640, 640).
        device: Target PyTorch execution device ('cpu' or 'cuda').

    Returns:
        dict containing:
            - 'tensor': PyTorch FloatTensor of shape [1, 3, target_h, target_w] normalized to [0.0, 1.0]
            - 'preprocessed_np': NumPy array of shape [target_h, target_w, 3] in RGB uint8
            - 'original_shape': (orig_height, orig_width)
            - 'scale_ratio': float resize factor
            - 'padding': (pad_width, pad_height) in pixels
    """
    # 1. Load image into standard RGB NumPy format
    if isinstance(image_input, (str, Path)):
        path_str = str(image_input)
        if not Path(path_str).exists():
            raise FileNotFoundError(f"Input image not found: {path_str}")
        bgr = cv2.imread(path_str)
        if bgr is None:
            raise ValueError(f"Failed to read image from path: {path_str}")
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    elif isinstance(image_input, Image.Image):
        rgb = np.array(image_input.convert("RGB"))
    elif isinstance(image_input, np.ndarray):
        if image_input.ndim == 2:
            rgb = cv2.cvtColor(image_input, cv2.COLOR_GRAY2RGB)
        elif image_input.shape[2] == 4:
            rgb = cv2.cvtColor(image_input, cv2.COLOR_RGBA2RGB)
        elif image_input.shape[2] == 3:
            # Assume RGB array
            rgb = image_input
        else:
            raise ValueError(f"Unsupported array shape: {image_input.shape}")
    else:
        raise TypeError(f"Unsupported image input type: {type(image_input)}")

    orig_shape = (rgb.shape[0], rgb.shape[1])  # (H, W)

    # 2. Apply letterbox resizing
    padded_rgb, ratio, (pad_w, pad_h) = letterbox_image(
        rgb, target_shape=target_size, fill_color=(114, 114, 114)
    )

    # 3. Transpose HWC -> CHW
    chw = padded_rgb.transpose((2, 0, 1))  # [3, H, W]
    chw = np.ascontiguousarray(chw)

    # 4. Convert to PyTorch Tensor & Normalize to [0.0, 1.0]
    tensor = torch.from_numpy(chw).to(device)
    tensor = tensor.float() / 255.0

    # 5. Add batch dimension: [1, 3, H, W]
    if tensor.ndimension() == 3:
        tensor = tensor.unsqueeze(0)

    return {
        "tensor": tensor,
        "preprocessed_np": padded_rgb,
        "original_shape": orig_shape,
        "scale_ratio": ratio,
        "padding": (pad_w, pad_h),
    }
