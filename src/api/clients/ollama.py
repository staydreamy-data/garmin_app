import requests
from src.api.core.settings import get_settings


class OllamaClient:
    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        timeout: int = 60,
    ) -> None:
        settings = get_settings()
        self.base_url = base_url or settings.ollama_url
        self.model = model or settings.ollama_model
        self.timeout = timeout

    def generate(
        self,
        prompt: str,
        num_predict: int = 1000,
        temperature: float = 0.3,
    ) -> dict:
        response = requests.post(
            f"{self.base_url}/api/generate",
            json={
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "num_predict": num_predict,
                    "temperature": temperature,
                },
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json()
