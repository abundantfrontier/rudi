import unittest
from unittest.mock import MagicMock, patch, AsyncMock
from core.llm.factory import LLMFactory
from core.llm.mlx_provider import MLXProvider
from core.llm.openai_provider import OpenAIProvider

class TestLLMIntegration(unittest.IsolatedAsyncioTestCase):
    def test_factory_defaults_mac(self):
        with patch("platform.system", return_value="Darwin"), \
             patch("platform.machine", return_value="arm64"):
            provider = LLMFactory.get_provider()
            self.assertIsInstance(provider, MLXProvider)

    def test_factory_defaults_linux(self):
        with patch("platform.system", return_value="Linux"):
            provider = LLMFactory.get_provider()
            self.assertIsInstance(provider, OpenAIProvider)

    def test_factory_override_openai(self):
        config = {"llm": {"provider": "openai", "model": "gpt-4"}}
        provider = LLMFactory.get_provider(config)
        self.assertIsInstance(provider, OpenAIProvider)
        self.assertEqual(provider.model_name, "gpt-4")

    @patch("openai.AsyncOpenAI")
    async def test_openai_provider_generate(self, mock_openai):
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        
        # Mock completion response
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="Hello world"))]
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        
        provider = OpenAIProvider(model_name="test-model")
        result = await provider.generate("Hi")
        
        self.assertEqual(result, "Hello world")
        mock_client.chat.completions.create.assert_called_once()

if __name__ == "__main__":
    unittest.main()
