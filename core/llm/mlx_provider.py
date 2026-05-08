import logging
import asyncio
from typing import Optional, Dict, Any
from core.llm.base import LLMProvider, LLMGenerationError, LLMError

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
        logger.info(f"Initialized MLXProvider with default model: {model_path}")

    def _ensure_loaded(self, progress_callback: Optional[callable] = None):
        if self.model is None:
            try:
                import mlx_lm
                import tqdm
                import sys
                
                logger.info(f"Loading MLX model: {self.model_path}...")
                
                # Custom tqdm to capture load progress
                class LoadProgressTqdm:
                    def __init__(self, iterable=None, *args, **kwargs):
                        self.iterable = iterable
                        self.total = kwargs.get('total')
                        if self.total is None and iterable is not None:
                            try: self.total = len(iterable)
                            except: self.total = 0
                        self.current = 0
                        self.desc = kwargs.get('desc', 'Loading')
                        self.n = 0
                    
                    def update(self, n=1):
                        self.current += n
                        self.n = self.current
                        if progress_callback:
                            percent = int((self.current / self.total) * 100) if self.total and self.total > 0 else 0
                            # Pass raw counts so UI can show MB
                            try:
                                progress_callback(self.desc, percent, "", self.current, self.total)
                            except:
                                progress_callback(self.desc, percent)
                    
                    def close(self): pass
                    def reset(self, total=None): 
                        if total is not None: self.total = total
                    def set_description(self, desc, refresh=True): self.desc = desc
                    def set_postfix(self, *args, **kwargs): pass
                    def get_lock(self): return None
                    def __enter__(self): return self
                    def __exit__(self, *args): pass
                    def __iter__(self):
                        if self.iterable:
                            for item in self.iterable:
                                yield item
                                self.update(1)
                        else:
                            yield from []
                    
                    # Catch-all
                    def __getattr__(self, name):
                        return lambda *args, **kwargs: None

                # Aggressive monkey-patch
                original_tqdm_class = tqdm.tqdm
                tqdm.tqdm = LoadProgressTqdm
                if 'tqdm' in sys.modules:
                    sys.modules['tqdm'].tqdm = LoadProgressTqdm
                    if hasattr(sys.modules['tqdm'], 'auto'):
                        sys.modules['tqdm'].auto.tqdm = LoadProgressTqdm

                try:
                    logger.info(f"Calling mlx_lm.load('{self.model_path}')...")
                    self.model, self.tokenizer = mlx_lm.load(self.model_path)
                    
                    # Ensure turn-ending tokens are registered
                    # Modern mlx-lm uses eos_token_ids for stopping
                    for token in ["<|eot_id|>", "<|im_end|>", "<|end_of_text|>"]:
                        try:
                            self.tokenizer.add_eos_token(token)
                        except: pass
                    
                    logger.info("mlx_lm.load() successfully returned model and tokenizer.")
                finally:
                    # Restore original
                    tqdm.tqdm = original_tqdm_class
                    if 'tqdm' in sys.modules:
                        sys.modules['tqdm'].tqdm = original_tqdm_class
                
                logger.info("MLX model weights successfully moved to RAM.")
                if progress_callback:
                    try:
                        progress_callback("Ready", 100, "", 1, 1)
                    except:
                        progress_callback("Ready", 100)
            except ImportError:
                raise LLMGenerationError("mlx-lm not installed. Run 'pip install mlx-lm'.")
            except Exception as e:
                logger.error(f"Error during MLX load: {e}", exc_info=True)
                raise LLMGenerationError(f"Failed to load MLX model: {e}")

    def download_model(self, model_path: Optional[str] = None, progress_callback: Optional[callable] = None):
        """
        Explicitly download/cache a model with progress reporting.
        """
        path = model_path or self.model_path
        try:
            from huggingface_hub import snapshot_download
            logger.info(f"Downloading MLX model snapshot: {path}...")
            
            # Custom tqdm-like class to capture progress
            class ProgressReporter:
                def __init__(self, callback, model_id, *args, **kwargs):
                    self.callback = callback
                    self.model_id = model_id
                    self.total = 0
                    self.current = 0
                    self.n = 0

                def update(self, n):
                    self.current += n
                    self.n = self.current
                    if self.callback:
                        percent = int((self.current / self.total) * 100) if self.total and self.total > 0 else 0
                        try:
                            self.callback(self.model_id, percent, "", self.current, self.total)
                        except:
                            try:
                                self.callback(self.model_id, percent)
                            except:
                                self.callback(self.model_id, percent, "")

                def close(self): pass
                def reset(self, total=None):
                    if total is not None: self.total = total
                def set_description(self, desc, refresh=True): pass
                def set_postfix(self, *args, **kwargs): pass
                def get_lock(self): return None
                def __enter__(self): return self
                def __exit__(self, *args): pass
                def __call__(self, iterable=None, total=None, *args, **kwargs):
                    self.total = total or 0
                    return self
                
                # Catch-all for any other tqdm methods to prevent crashes
                def __getattr__(self, name):
                    return lambda *args, **kwargs: None

            reporter = ProgressReporter(progress_callback, path)
            
            # snapshot_download uses tqdm if available, we can pass our reporter
            snapshot_download(repo_id=path, tqdm_class=reporter)
            
            logger.info(f"Model {path} downloaded successfully.")
            if progress_callback:
                try:
                    progress_callback(path, 100, "", 1, 1)
                except:
                    try:
                        progress_callback(path, 100)
                    except:
                        progress_callback(path, 100, "")
            return True
        except Exception as e:
            logger.error(f"Failed to download model {path}: {e}")
            if progress_callback:
                try:
                    progress_callback(path, -1, str(e), 0, 0)
                except:
                    try:
                        progress_callback(path, -1, str(e))
                    except:
                        progress_callback(path, -1)
            return False

    def search_models(self, query: str) -> list[Dict[str, Any]]:
        """
        Search HuggingFace for MLX-compatible models with robust fallback.
        """
        logger.info(f"Searching for models matching: '{query}'")
        try:
            from huggingface_hub import HfApi
        except ImportError:
            logger.error("huggingface_hub not installed.")
            raise LLMError("Model search requires 'huggingface-hub'. Run 'pip install huggingface-hub'.")

        try:
            api = HfApi()
            
            # Strategy 1: If it looks like a repo ID, try exact match
            if "/" in query:
                try:
                    m = api.model_info(query)
                    return [{
                        "id": m.id,
                        "downloads": getattr(m, "downloads", 0),
                        "last_modified": str(getattr(m, "last_modified", "")),
                    }]
                except:
                    pass # Not an exact ID, continue to search

            # Strategy 2: Targeted MLX search
            search_query = query
            if "mlx" not in query.lower():
                search_query = f"{query} mlx"
                
            logger.info(f"Executing Targeted search: '{search_query}'")
            models = list(api.list_models(search=search_query, sort="downloads", limit=20))
            
            # Strategy 3: Fallback to broader search if nothing found
            if not models:
                logger.info(f"Targeted search returned 0 results. Falling back to broad search: '{query}'")
                models = list(api.list_models(search=query, sort="downloads", limit=20))
                # Filter for MLX in name if we fell back
                models = [m for m in models if "mlx" in m.id.lower()]
            
            logger.info(f"HF API returned {len(models)} results after filtering.")
            
            results = []
            for m in models:
                results.append({
                    "id": m.id,
                    "downloads": getattr(m, "downloads", 0),
                    "last_modified": str(getattr(m, "last_modified", "")),
                })
            
            return results
        except Exception as e:
            logger.error(f"Model search failed: {e}", exc_info=True)
            return []

    def list_local_models(self) -> list[str]:
        """
        List MLX models already in the local HuggingFace cache.
        """
        try:
            from huggingface_hub import scan_cache_dir
            cache_info = scan_cache_dir()
            local_models = []
            for repo in cache_info.repos:
                if "mlx" in repo.repo_id.lower():
                    local_models.append(repo.repo_id)
            return sorted(local_models)
        except Exception as e:
            logger.error(f"Failed to list local models: {e}")
            return []

    async def generate(
        self, 
        prompt: Any, 
        system_prompt: Optional[str] = None, 
        temperature: float = 0.7, 
        max_tokens: int = 1000, 
        json_mode: bool = False
    ) -> str:
        self._ensure_loaded()
        import mlx_lm
        from mlx_lm.sample_utils import make_sampler

        full_prompt = ""
        
        # Support both raw string and list of messages
        if isinstance(prompt, list):
            # Check for chat template
            if hasattr(self.tokenizer, "apply_chat_template"):
                messages = []
                if system_prompt:
                    messages.append({"role": "system", "content": system_prompt})
                messages.extend(prompt)
                full_prompt = self.tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
            else:
                # Manual fallback
                full_prompt = f"{system_prompt}\n" if system_prompt else ""
                for msg in prompt:
                    full_prompt += f"{msg['role'].upper()}: {msg['content']}\n"
                full_prompt += "ASSISTANT: "
        else:
            # Raw string prompt
            full_prompt = prompt
            if system_prompt:
                # Default to Llama-3 style if not templated
                full_prompt = f"<|begin_of_text|><|start_header_id|>system<|end_header_id|>\n\n{system_prompt}<|eot_id|><|start_header_id|>user<|end_header_id|>\n\n{prompt}<|eot_id|><|start_header_id|>assistant<|end_header_id|>\n\n"

        try:
            # Modern versions (0.31+) expect a sampler object
            sampler = make_sampler(temp=temperature)
            
            response = mlx_lm.generate(
                self.model, 
                self.tokenizer, 
                prompt=full_prompt, 
                sampler=sampler,
                max_tokens=max_tokens
            )
            return response.strip()
        except Exception as e:
            logger.error(f"MLX generation failed: {e}", exc_info=True)
            raise LLMGenerationError(f"MLX generation failed: {e}")
