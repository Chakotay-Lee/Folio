import json
import logging
import httpx
from backend.llm.base import LLMProvider
from backend.llm.prompts import build_extraction_prompt

logger = logging.getLogger(__name__)


class OllamaProvider(LLMProvider):
    def __init__(self, model_name: str, base_url: str, temperature: float, max_tokens: int, timeout_seconds: int, api_key: str = "", **_):
        self.model_name = model_name
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout_seconds = timeout_seconds

    def _raw_generate(self, prompt: str, max_tokens: int | None = None) -> str:
        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": self.temperature, "num_predict": max_tokens or self.max_tokens},
        }
        response = httpx.post(
            f"{self.base_url}/api/generate",
            json=payload,
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        return response.json().get("response", "")

    def complete(self, prompt: str, max_tokens: int | None = None) -> str:
        return self._raw_generate(prompt, max_tokens=max_tokens)

    def extract_metadata(self, text: str, existing_genres: list[str] | None = None, filename_hint: str | None = None, language: str = "en") -> dict:
        prompt = build_extraction_prompt(text, existing_genres, filename_hint=filename_hint, language=language)
        raw = self._raw_generate(prompt)
        return json.loads(raw)
