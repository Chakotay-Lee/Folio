import json
import logging
from backend.llm.base import LLMProvider
from backend.llm.prompts import build_extraction_prompt

logger = logging.getLogger(__name__)


class AnthropicProvider(LLMProvider):
    def __init__(self, model_name: str, api_key: str, temperature: float, max_tokens: int, timeout_seconds: int, **_):
        import anthropic
        self.client = anthropic.Anthropic(api_key=api_key, timeout=timeout_seconds)
        self.model_name = model_name
        self.temperature = temperature
        self.max_tokens = max_tokens

    def extract_metadata(self, text: str, existing_genres: list[str] | None = None, filename_hint: str | None = None, language: str = "en") -> dict:
        prompt = build_extraction_prompt(text, existing_genres, filename_hint=filename_hint, language=language)
        message = self.client.messages.create(
            model=self.model_name,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            messages=[{"role": "user", "content": prompt}],
        )
        content = message.content[0].text
        start = content.find("{")
        end = content.rfind("}") + 1
        return json.loads(content[start:end])
