from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class LLMResponse:
    content: str
    model: str
    provider: str
    usage: dict = field(default_factory=dict)
    raw: dict | None = None


class LLMProvider(ABC):
    """Base class for all LLM providers."""

    provider_name: str = "base"

    @abstractmethod
    async def complete(
        self,
        prompt: str,
        system: str = "",
        model: str | None = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> LLMResponse: ...

    @abstractmethod
    async def is_available(self) -> bool: ...
