import os
from typing import AsyncIterator, List
from groq import Groq
from app.config import settings

_groq_client: Groq | None = None

def get_groq_client() -> Groq:
    global _groq_client
    if _groq_client is None:
        key = settings.groq_api_key or os.environ.get("GROQ_API_KEY")
        if not key:
            raise RuntimeError("GROQ_API_KEY not configured")
        _groq_client = Groq(api_key=key)
    return _groq_client

class GroqLLM:
    def __init__(self):
        self.client = get_groq_client()
        self.model = settings.groq_model

    def chat(self, messages: List[dict], temperature: float | None = None, max_tokens: int | None = None) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature if temperature is not None else settings.groq_temperature,
            max_tokens=max_tokens if max_tokens is not None else settings.groq_max_tokens,
        )
        return response.choices[0].message.content or ""

    async def chat_stream(self, messages: List[dict], temperature: float | None = None, max_tokens: int | None = None) -> AsyncIterator[str]:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature if temperature is not None else settings.groq_temperature,
            max_tokens=max_tokens if max_tokens is not None else settings.groq_max_tokens,
            stream=True,
        )
        for chunk in response:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta

    def classify(self, prompt: str, labels: List[str]) -> str:
        system = (
            "You are a strict classifier. Respond with exactly one of the following labels: "
            + ", ".join(labels)
            + ". No extra text."
        )
        text = self.chat([{"role": "system", "content": system}, {"role": "user", "content": prompt}])
        text = text.strip().lower()
        for label in labels:
            if label.lower() in text:
                return label
        return labels[0]

    def judge_yes_no(self, prompt: str) -> bool:
        system = "Answer only Yes or No."
        text = self.chat([{"role": "system", "content": system}, {"role": "user", "content": prompt}])
        return "yes" in text.strip().lower()
