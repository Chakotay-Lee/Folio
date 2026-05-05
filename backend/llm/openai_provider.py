import json
import logging
from backend.llm.base import LLMProvider
from backend.llm.prompts import build_extraction_prompt

logger = logging.getLogger(__name__)


class OpenAIProvider(LLMProvider):
    def __init__(self, model_name: str, api_key: str, temperature: float, max_tokens: int,
                 timeout_seconds: int, base_url: str = "", extra_body: dict | None = None, **_):
        from openai import OpenAI
        kwargs: dict = {"api_key": api_key, "timeout": float(timeout_seconds)}
        if base_url:
            kwargs["base_url"] = base_url
        self.client = OpenAI(**kwargs)
        self.model_name = model_name
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.extra_body = extra_body or {}

    def extract_metadata(self, text: str, existing_genres: list[str] | None = None,
                         filename_hint: str | None = None, language: str = "en") -> dict:
        prompt = build_extraction_prompt(text, existing_genres, filename_hint=filename_hint, language=language)
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=[{"role": "user", "content": prompt}],
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            extra_body=self.extra_body or None,
        )
        raw = response.choices[0].message.content or ""
        # Extract JSON block in case model wraps it in markdown fences
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start == -1:
            raise ValueError(f"No JSON found in LLM response: {raw[:200]}")
        return json.loads(raw[start:end])
