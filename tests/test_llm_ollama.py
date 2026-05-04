import json

import pytest
import requests

from app.llm import OllamaClient, OllamaResponseError, OllamaUnavailableError
from app.matching.llm import LLMRerankPayload


class DummyResponse:
    def __init__(self, payload, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"status={self.status_code}")

    def json(self):
        return self._payload


def test_ollama_client_parses_structured_chat_response(monkeypatch) -> None:
    client = OllamaClient(
        base_url="http://localhost:11434",
        timeout_seconds=10.0,
        default_model="qwen3:4b",
    )

    def fake_post(*args, **kwargs):
        return DummyResponse(
            {
                "message": {
                    "content": json.dumps(
                        {
                            "fit_score": 88,
                            "decision": "strong_match",
                            "matched_skills": ["Python"],
                            "missing_skills": ["TensorFlow"],
                            "seniority_fit": "target_level",
                            "location_fit": "target_location",
                            "short_reason": "Strong ML overlap",
                        }
                    )
                }
            }
        )

    monkeypatch.setattr(requests, "post", fake_post)

    payload = client.generate_structured(
        model=None,
        system_prompt="system",
        user_prompt="user",
        schema_model=LLMRerankPayload,
    )

    assert payload.fit_score == 88
    assert payload.decision == "strong_match"


def test_ollama_client_raises_on_invalid_json_content(monkeypatch) -> None:
    client = OllamaClient(
        base_url="http://localhost:11434",
        timeout_seconds=10.0,
        default_model="qwen3:4b",
    )

    monkeypatch.setattr(
        requests,
        "post",
        lambda *args, **kwargs: DummyResponse({"message": {"content": "not-json"}}),
    )

    with pytest.raises(OllamaResponseError):
        client.generate_structured(
            model=None,
            system_prompt="system",
            user_prompt="user",
            schema_model=LLMRerankPayload,
        )


def test_ollama_client_raises_when_runtime_unavailable(monkeypatch) -> None:
    client = OllamaClient(
        base_url="http://localhost:11434",
        timeout_seconds=10.0,
        default_model="qwen3:4b",
    )

    def fake_post(*args, **kwargs):
        raise requests.ConnectionError("offline")

    monkeypatch.setattr(requests, "post", fake_post)

    with pytest.raises(OllamaUnavailableError):
        client.generate_structured(
            model=None,
            system_prompt="system",
            user_prompt="user",
            schema_model=LLMRerankPayload,
        )
