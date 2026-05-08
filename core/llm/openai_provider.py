import logging
from typing import Optional, Dict, Any
from core.llm.base import LLMProvider, LLMGenerationError

logger = logging.getLogger("rudi.llm.openai")

class OpenAIProvider(LLMProvider):
    """
    LLM provider using the OpenAI-compatible API (Ollama, LM Studio, etc.).
    """
    def __init__(
        self, 
        model_name: str = "llama3", 
        base_url: str = "http://localhost:11434/v1", 
        api_key: str = "ollama"
    ):
        self.model_name = model_name
        self.base_url = base_url
        self.api_key = api_key
        self.client = None

    def _get_client(self):
        if self.client is None:
            try:
                from openai import AsyncOpenAI
                self.client = AsyncOpenAI(base_url=self.base_url, api_key=self.api_key)
            except ImportError:
                raise LLMGenerationError("openai library not installed. Run 'pip install openai'.")
        return self.client

    def search_models(self, query: str) -> list[Dict[str, Any]]:
        """
        OpenAI-compatible endpoints (Ollama, LM Studio) don't standardly expose
        a central search hub via the V1 API.
        """
        return []

    def list_local_models(self) -> list[str]:
        return []

    def download_model(self, model_path: Optional[str] = None, progress_callback: Optional[callable] = None) -> bool:
        return False

    async def generate(
        self, 
        prompt: str, 
        system_prompt: Optional[str] = None, 
        temperature: float = 0.7, 
        max_tokens: int = 1000, 
        json_mode: bool = False
    ) -> str:
        client = self._get_client()
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response_format = None
        if json_mode:
            response_format = {"type": "json_object"}

        try:
            completion = await client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format=response_format
            )
            return completion.choices[0].message.content.strip()
        except Exception as e:
            raise LLMGenerationError(f"OpenAI-compatible generation failed: {e}")
