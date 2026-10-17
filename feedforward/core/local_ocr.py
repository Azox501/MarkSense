"""Local OCR for scanned teacher resources; this path never calls Gemini."""
from collections.abc import Iterable
from functools import lru_cache
from io import BytesIO
import os
from typing import Any

import numpy as np
from PIL import Image

from core.config import AppError, get_settings


@lru_cache(maxsize=1)
def ocr_engine() -> Any:
    """Load compact English PaddleOCR models once per Streamlit process."""
    try:
        model_directory = get_settings(False).data_dir / "models" / "paddleocr"
        model_directory.mkdir(parents=True, exist_ok=True)
        os.environ.setdefault("PADDLE_PDX_CACHE_HOME", str(model_directory))
        from paddleocr import PaddleOCR
        return PaddleOCR(
            text_detection_model_name="PP-OCRv5_mobile_det",
            text_recognition_model_name="en_PP-OCRv5_mobile_rec",
            # PaddlePaddle 3.3.1 has a Windows oneDNN/PIR inference defect.
            # Explicitly use the compatible standard CPU execution path.
            enable_mkldnn=False,
        )
    except Exception as exc:
        raise AppError("Local OCR could not start. Restart MarkSense after PaddleOCR finishes its first model download.") from exc


def _payload(result: Any) -> dict[str, Any]:
    """Normalize PaddleOCR v3 result objects without coupling callers to its SDK shape."""
    if isinstance(result, dict):
        return result
    value = getattr(result, "json", None)
    if callable(value):
        value = value()
    if isinstance(value, dict):
        return value
    value = getattr(result, "to_dict", None)
    if callable(value):
        value = value()
    return value if isinstance(value, dict) else {}


def _lines(results: Iterable[Any]) -> list[str]:
    """Extract recognized text from current PaddleOCR results or legacy list results."""
    text: list[str] = []
    for result in results:
        payload = _payload(result)
        recognized = payload.get("rec_texts") or payload.get("text") or []
        if isinstance(recognized, str):
            recognized = [recognized]
        text.extend(item.strip() for item in recognized if isinstance(item, str) and item.strip())
        if not payload and isinstance(result, list):
            candidates = [result] if len(result) > 1 and isinstance(result[1], (list, tuple)) else result
            text.extend(line[1][0].strip() for line in candidates
                        if isinstance(line, (list, tuple)) and len(line) > 1 and isinstance(line[1], (list, tuple))
                        and line[1] and isinstance(line[1][0], str) and line[1][0].strip())
    return text


def recognize_image(image_bytes: bytes) -> str:
    """Return the readable text of one scanned page using local PaddleOCR."""
    try:
        image = np.asarray(Image.open(BytesIO(image_bytes)).convert("RGB"))
        engine = ocr_engine()
        results = engine.predict(image) if hasattr(engine, "predict") else engine.ocr(image, cls=True)
        text = "\n".join(_lines(results))
    except AppError:
        raise
    except Exception as exc:
        raise AppError("Local OCR could not read this scanned page. Use a clearer PDF or try again.") from exc
    if len(text.strip()) < 1:
        raise AppError("Local OCR could not find readable text on this page. Use a clearer PDF.")
    return text
