import logging

from config.settings import settings
from services.llm.base import LLMProvider, LLMResponse
from services.llm.providers.claude import ClaudeProvider
from services.llm.providers.gemini import GeminiProvider
from services.llm.providers.ollama import OllamaProvider

log = logging.getLogger(__name__)


class LLMRouter:
    """Routes LLM requests to the appropriate provider.

    Privacy model:
    1. Sensitive screening ALWAYS runs on local Ollama (nothing leaves your machine).
    2. Non-sensitive content can optionally be routed to cloud providers for
       higher quality analysis.
    3. You control the routing per-task via the provider parameter.
    """

    def __init__(self):
        self._providers: dict[str, LLMProvider] = {}
        self._init_providers()

    def _init_providers(self):
        self._providers["ollama"] = OllamaProvider()
        if settings.claude_api_key:
            self._providers["claude"] = ClaudeProvider()
        if settings.gemini_api_key:
            self._providers["gemini"] = GeminiProvider()

    def get_provider(self, name: str | None = None) -> LLMProvider:
        name = name or settings.default_provider.value
        if name not in self._providers:
            available = list(self._providers.keys())
            raise ValueError(f"Provider '{name}' not available. Available: {available}")
        return self._providers[name]

    async def complete(
        self,
        prompt: str,
        system: str = "",
        provider: str | None = None,
        model: str | None = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        """Send a completion request to the specified (or default) provider."""
        p = self.get_provider(provider)
        log.info(f"Routing to {p.provider_name} (model={model or 'default'})")
        return await p.complete(
            prompt=prompt,
            system=system,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    async def screen_then_analyze(
        self,
        content: str,
        screening_prompt: str,
        analysis_prompt: str,
        analysis_provider: str | None = None,
    ) -> dict:
        """Privacy-first two-pass processing.

        Pass 1: Local model screens for sensitive content (PII, financial, medical).
        Pass 2: If clean, optionally route to a cloud model for deeper analysis.
                 If sensitive, keep everything local.
        """
        # Pass 1: always local
        screening = await self.complete(
            prompt=screening_prompt.format(content=content),
            provider="ollama",
            temperature=0.1,
        )

        is_sensitive = "SENSITIVE" in screening.content.upper()

        if is_sensitive:
            log.info("Content flagged sensitive — keeping analysis local")
            analysis = await self.complete(
                prompt=analysis_prompt.format(content=content),
                provider="ollama",
            )
        else:
            target = analysis_provider or settings.high_quality_provider.value
            # Fall back to ollama if the cloud provider isn't configured
            if target not in self._providers:
                target = "ollama"
            log.info(f"Content clean — routing analysis to {target}")
            analysis = await self.complete(
                prompt=analysis_prompt.format(content=content),
                provider=target,
            )

        return {
            "screening": screening,
            "analysis": analysis,
            "kept_local": is_sensitive,
        }

    async def health(self) -> dict:
        result = {}
        for name, provider in self._providers.items():
            result[name] = await provider.is_available()
        return result


# Singleton instance
llm_router = LLMRouter()
