import platform
import logging
from typing import Optional, Dict, Any
from core.llm.base import LLMProvider
from core.llm.mlx_provider import MLXProvider
from core.llm.openai_provider import OpenAIProvider

logger = logging.getLogger("rudi.llm.factory")

class LLMFactory:
    @staticmethod
    def get_provider(config: Optional[dict] = None) -> LLMProvider:
        """
        Create and return an LLM provider based on OS and config.
        Default: MLX on macOS (Apple Silicon), OpenAI elsewhere.
        """
        config = config or {}
        llm_config = config.get("llm", {})
        provider_type = llm_config.get("provider")

        # Explicit override
        if provider_type == "mlx":
            return MLXProvider(model_path=llm_config.get("model", "mlx-community/Meta-Llama-3-8B-Instruct-4bit"))
        elif provider_type == "openai":
            return OpenAIProvider(
                model_name=llm_config.get("model", "llama3"),
                base_url=llm_config.get("base_url", "http://localhost:11434/v1"),
                api_key=llm_config.get("api_key", "ollama")
            )

        # Default logic
        os_name = platform.system().lower()
        machine = platform.machine().lower()

        if os_name == "darwin" and machine == "arm64":
            logger.info("Defaulting to MLX provider on Apple Silicon.")
            return MLXProvider()
        else:
            logger.info(f"Defaulting to OpenAI-compatible provider on {os_name}.")
            return OpenAIProvider()
