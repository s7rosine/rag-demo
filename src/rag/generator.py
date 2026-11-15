"""Generate responses with local Ollama."""
import requests

class Generator:
    def __init__(self, url="http://localhost:11434", model="llama3.2:1b"):
        self.url, self.model = url.rstrip("/"), model

    def generate(self, prompt: str) -> str:
        response = requests.post(
            f"{self.url}/api/generate",
            json={"model": self.model, "prompt": prompt, "stream": False},
            timeout=180,
        )
        response.raise_for_status()
        return response.json()["response"]
