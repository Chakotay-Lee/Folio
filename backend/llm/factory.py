from backend.llm.base import LLMProvider
from backend.config_loader import LLMModelConfig


def get_provider(config: LLMModelConfig) -> LLMProvider:
    kwargs = {
        "model_name": config.model_name,
        "api_key": config.api_key,
        "temperature": config.temperature,
        "max_tokens": config.max_tokens,
        "timeout_seconds": config.timeout_seconds,
        "base_url": config.base_url,
        "extra_body": config.extra_body,
    }
    provider = config.provider.lower()
    if provider == "ollama":
        from backend.llm.ollama_provider import OllamaProvider
        return OllamaProvider(**kwargs)
    if provider == "openai":
        from backend.llm.openai_provider import OpenAIProvider
        return OpenAIProvider(**kwargs)
    if provider == "anthropic":
        from backend.llm.anthropic_provider import AnthropicProvider
        return AnthropicProvider(**kwargs)
    raise ValueError(f"Unknown LLM provider: '{provider}'. Supported: ollama, openai, anthropic")
