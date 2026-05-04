from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, TypeVar

import requests
from pydantic import BaseModel, ValidationError


class OllamaError(RuntimeError):
    """Base error for Ollama integration failures."""


class OllamaUnavailableError(OllamaError):
    """Raised when the local Ollama runtime cannot be reached."""


class OllamaResponseError(OllamaError):
    """Raised when Ollama returns malformed or invalid structured output."""


StructuredModelT = TypeVar("StructuredModelT", bound=BaseModel)


@dataclass(frozen=True, slots=True)
class OllamaClient:
    base_url: str
    timeout_seconds: float
    default_model: str

    def generate_structured(
        self,
        *,
        model: str | None,
        system_prompt: str,
        user_prompt: str,
        schema_model: type[StructuredModelT],
        temperature: float = 0.1,
    ) -> StructuredModelT:
        schema = schema_model.model_json_schema()
        payload = {
            "model": model or self.default_model,
            "stream": False,
            "format": schema,
            "options": {"temperature": temperature},
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }

        try:
            response = requests.post(
                f"{self.base_url.rstrip('/')}/api/chat",
                json=payload,
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise OllamaUnavailableError(f"Ollama request failed: {exc}") from exc

        response_payload = response.json()
        content = self._extract_message_content(response_payload)
        try:
            decoded = json.loads(content)
        except json.JSONDecodeError as exc:
            raise OllamaResponseError(
                f"Ollama returned non-JSON content: {exc.msg}"
            ) from exc

        try:
            return schema_model.model_validate(decoded)
        except ValidationError as exc:
            raise OllamaResponseError(f"Ollama returned invalid structured output: {exc}") from exc

    def _extract_message_content(self, payload: Any) -> str:
        if not isinstance(payload, dict):
            raise OllamaResponseError("Ollama response payload must be a JSON object")

        message = payload.get("message")
        if isinstance(message, dict) and isinstance(message.get("content"), str):
            return message["content"]

        if isinstance(payload.get("response"), str):
            return payload["response"]

        raise OllamaResponseError("Ollama response payload did not include message content")
