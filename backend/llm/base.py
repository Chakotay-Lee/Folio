from abc import ABC, abstractmethod


class LLMProvider(ABC):
    @abstractmethod
    def extract_metadata(self, text: str, existing_genres: list[str] | None = None,
                         filename_hint: str | None = None, language: str = "en") -> dict:
        """Return dict with keys: title, author, summary, tags, genre_path."""

    def complete(self, prompt: str, max_tokens: int | None = None) -> str:
        """Return raw text completion for an arbitrary prompt."""
        raise NotImplementedError
