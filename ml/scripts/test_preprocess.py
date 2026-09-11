"""Unit test for ml/src/preprocess.py"""

import os
import sys
from pathlib import Path
import torch
import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.preprocess import preprocess_report_image, letterbox_image


def test_preprocessing():
    print("[TEST] Running Preprocessing Pipeline Verification...")
    
    # 1. Test with synthetic PIL image
    dummy_img = Image.new("RGB", (1280, 720), color=(100, 150, 200))
    result = preprocess_report_image(dummy_img, target_size=(640, 640))
    
    tensor = result["tensor"]
    assert isinstance(tensor, torch.Tensor), "Output tensor is not a torch.Tensor"
    assert tensor.shape == (1, 3, 640, 640), f"Unexpected tensor shape: {tensor.shape}"
    assert tensor.dtype == torch.float32, f"Unexpected dtype: {tensor.dtype}"
    assert 0.0 <= tensor.min().item() <= tensor.max().item() <= 1.0, "Tensor values not normalized in [0, 1]"
    assert result["original_shape"] == (720, 1280), f"Unexpected original shape: {result['original_shape']}"
    print("   [OK] Synthetic image preprocessing passed: shape [1, 3, 640, 640], normalized.")

    # 2. Test with real sample image from Dataset if available
    sample_dir = Path(__file__).resolve().parents[2] / "Dataset" / "RDD_SPLIT" / "train" / "images"
    if sample_dir.exists():
        sample_files = list(sample_dir.glob("*.jpg")) + list(sample_dir.glob("*.png"))
        if sample_files:
            real_sample = sample_files[0]
            real_result = preprocess_report_image(str(real_sample), target_size=(640, 640))
            real_tensor = real_result["tensor"]
            assert real_tensor.shape == (1, 3, 640, 640)
            print(f"   [OK] Real RDD2022 dataset image '{real_sample.name}' preprocessed successfully: shape {real_tensor.shape}.")

    print("ALL PREPROCESSING TESTS PASSED! [100%]")


if __name__ == "__main__":
    test_preprocessing()
