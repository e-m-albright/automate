import logging

from config.settings import settings
from services.llm.base import LLMProvider, LLMResponse

log = logging.getLogger(__name__)


class ClaudeProvider(LLMProvider):
    """Anthropic Claude provider — high quality analysis for non-sensitive content."""

    provider_name = "claude"

    def __init__(self, api_key: str | None = None, model: str | None = None):
        self.api_key = api_key or settings.claude_api_key
        self.default_model = model or settings.claude_model

    async def complete(
        self,
        prompt: str,
        system: str = "",
        model: str | None = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        import anthropic

        model = model or self.default_model
        client = anthropic.AsyncAnthropic(api_key=self.api_key)

        kwargs = {
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            kwargs["system"] = system

        message = await client.messages.create(**kwargs)

        return LLMResponse(
            content=message.content[0].text,
            model=model,
            provider=self.provider_name,
            usage={
                "prompt_tokens": message.usage.input_tokens,
                "completion_tokens": message.usage.output_tokens,
            },
        )

    async def is_available(self) -> bool:
        return bool(self.api_key)
