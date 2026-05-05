import base64
import logging

logger = logging.getLogger(__name__)

_config = None


def init_ocr(config) -> None:
    global _config
    _config = config


def run_ocr(img_bytes: bytes) -> str:
    if _config is None:
        logger.warning("OCR not initialised — call init_ocr(config) first")
        return ""

    # Use dedicated ocr_model if configured, otherwise fall back to extraction_model
    model_cfg = _config.llms.ocr_model or _config.llms.extraction_model
    if not model_cfg:
        logger.warning("No OCR model configured")
        return ""

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
        logger.error("VLM OCR failed: %s", e)
        return ""
