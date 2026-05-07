from abc import ABC, abstractmethod
from typing import Optional, Dict, Any

class LLMError(Exception):
    """Base class for LLM-related errors."""
    pass

class LLMGenerationError(LLMError):
    """Raised when text generation fails."""
    pass

class LLMProvider(ABC):
    @abstractmethod
    async def generate(
        self, 
        prompt: str, 
        system_prompt: Optional[str] = None, 
        temperature: float = 0.7, 
        max_tokens: int = 1000, 
        json_mode: bool = False
    ) -> str:
        """
        Generate text based on a prompt and optional system prompt.
        """
        pass
