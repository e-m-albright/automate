import logging

from config.settings import settings
from services.llm.base import LLMProvider, LLMResponse

log = logging.getLogger(__name__)


class GeminiProvider(LLMProvider):
    """Google Gemini provider — can process YouTube videos, good multimodal."""

    provider_name = "gemini"

    def __init__(self, api_key: str | None = None, model: str | None = None):
        self.api_key = api_key or settings.gemini_api_key
        self.default_model = model or settings.gemini_model

    async def complete(
        self,
        prompt: str,
        system: str = "",
        model: str | None = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        import google.generativeai as genai

        model_name = model or self.default_model
        genai.configure(api_key=self.api_key)

        gen_model = genai.GenerativeModel(
            model_name=model_name,
            system_instruction=system if system else None,
        )

        response = await gen_model.generate_content_async(
            prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=temperature,
                max_output_tokens=max_tokens,
            ),
        )

        return LLMResponse(
            content=response.text,
            model=model_name,
            provider=self.provider_name,
            usage={},
        )

    async def is_available(self) -> bool:
        return bool(self.api_key)
