import logging
from typing import Optional, Dict, Any
from core.llm.base import LLMProvider, LLMGenerationError

logger = logging.getLogger("rudi.llm.mlx")

class MLXProvider(LLMProvider):
    """
    LLM provider using mlx-lm for local inference on Apple Silicon.
    Supports lazy loading and model caching.
    """
    def __init__(self, model_path: str = "mlx-community/Meta-Llama-3-8B-Instruct-4bit"):
        self.model_path = model_path
        self.model = None
        self.tokenizer = None

    def _ensure_loaded(self):
        if self.model is None:
            try:
                import mlx_lm
                logger.info(f"Loading MLX model: {self.model_path}...")
                # load() handles download automatically if not cached
                self.model, self.tokenizer = mlx_lm.load(self.model_path)
                logger.info("MLX model loaded successfully.")
            except ImportError:
                raise LLMGenerationError("mlx-lm not installed. Run 'pip install mlx-lm'.")
            except Exception as e:
                raise LLMGenerationError(f"Failed to load MLX model: {e}")

    async def download_model(self, model_path: Optional[str] = None):
        """
        Explicitly download/cache a model without loading it into memory for inference.
        """
        path = model_path or self.model_path
        try:
            from huggingface_hub import snapshot_download
            logger.info(f"Downloading MLX model snapshot: {path}...")
            # mlx-lm models are typically standard HF snapshots
            snapshot_download(repo_id=path)
            logger.info(f"Model {path} downloaded successfully.")
            return True
        except Exception as e:
            logger.error(f"Failed to download model {path}: {e}")
            return False

    async def generate(
        self, 
        prompt: str, 
        system_prompt: Optional[str] = None, 
        temperature: float = 0.7, 
        max_tokens: int = 1000, 
        json_mode: bool = False
    ) -> str:
        self._ensure_loaded()
        import mlx_lm

        full_prompt = prompt
        if system_prompt:
            # Simple instruction format for Llama-3 style instruct models
            # In a production app, we'd use the tokenizer's chat template.
            full_prompt = f"<|begin_of_text|><|start_header_id|>system<|end_header_id|>\n\n{system_prompt}<|eot_id|><|start_header_id|>user<|end_header_id|>\n\n{prompt}<|eot_id|><|start_header_id|>assistant<|end_header_id|>\n\n"

        try:
            # mlx_lm.generate is typically synchronous, so we'll wrap it or use it directly
            # depending on the mlx-lm version. For 0.12+, it's efficient.
            response = mlx_lm.generate(
                self.model, 
                self.tokenizer, 
                prompt=full_prompt, 
                temp=temperature, 
                max_tokens=max_tokens
            )
            return response.strip()
        except Exception as e:
            raise LLMGenerationError(f"MLX generation failed: {e}")
