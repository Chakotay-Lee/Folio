import base64
import logging

logger = logging.getLogger(__name__)

_config = None


def init_ocr(config) -> None:
    global _config
    _config = config


def run_ocr(img_bytes: bytes) -> str:
    if _config is None:
        raise RuntimeError("OCR not initialised — call init_ocr(config) first")

    model_cfg = _config.llms.ocr_model
    if not model_cfg:
        raise RuntimeError(
            "No VLM configured for OCR. Add 'ocr_model' under 'llms' in config.json "
            "pointing to a vision-capable model (e.g. Qwen3.5-VL). "
            "OCR on scanned pages requires a VLM — refusing to fall back to a text-only model."
        )

    try:
        from openai import OpenAI
        client = OpenAI(
            api_key=model_cfg.api_key,
            base_url=model_cfg.base_url,
            timeout=float(model_cfg.timeout_seconds),
        )
        b64 = base64.b64encode(img_bytes).decode("utf-8")
        response = client.chat.completions.create(
            model=model_cfg.model_name,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{b64}"},
                    },
                    {
                        "type": "text",
                        "text": "請提取圖片中的所有文字，原樣輸出，不要任何說明。",
                    },
                ],
            }],
            max_tokens=2048,
        )
        return response.choices[0].message.content or ""
    except Exception as e:
        raise RuntimeError(f"VLM OCR failed ({model_cfg.model_name}): {e}") from e
