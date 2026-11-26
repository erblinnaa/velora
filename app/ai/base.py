from abc import ABC, abstractmethod
from typing import Any


class AIProvider(ABC):
    """Small provider contract so the application is not tied to Ollama."""

    name = "unknown"

    @property
    @abstractmethod
    def model(self) -> str:
        """Return the configured model identifier."""

    @abstractmethod
    def generate_json(self, system_prompt: str, user_prompt: str) -> Any:
        """Generate and decode one JSON response."""

    @abstractmethod
    def healthcheck(self) -> dict:
        """Return provider availability information using a lightweight check."""
