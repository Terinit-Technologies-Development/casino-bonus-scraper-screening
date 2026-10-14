"""Offline validation and an opt-in synthetic live Gemini diagnostic."""

from __future__ import annotations

import json

import pytest
from google.genai import errors

from src import gemini_client


class FakeModels:
    def __init__(self, response_text: str | None = None, error: Exception | None = None):
        self.response_text = response_text
        self.error = error
        self.request: dict[str, object] | None = None

    def generate_content(self, **kwargs: object) -> object:
        self.request = kwargs
        if self.error is not None:
            raise self.error
        return type("FakeResponse", (), {"text": self.response_text})()


class FakeClient:
    def __init__(self, models: FakeModels):
        self.models = models


def test_extract_uses_schema_and_returns_expected_fields() -> None:
    terms = {
        "welcome_bonus": "100% first-deposit match up to R2,000",
        "wagering_requirement_multiplier": "10x casino bonus",
        "minimum_deposit": "R50",
    }
    models = FakeModels(json.dumps(terms))

    result = gemini_client.extract_bonus_terms(
        "Synthetic offer terms", client=FakeClient(models)  # type: ignore[arg-type]
    )

    assert result == terms
    assert models.request is not None
    assert models.request["model"] == gemini_client.MODEL_ID
    config = models.request["config"]
    assert config.response_mime_type == "application/json"
    assert config.response_json_schema == gemini_client.BONUS_TERMS_SCHEMA


@pytest.mark.parametrize(
    "response_text",
    [None, "not-json", "[]", '{"welcome_bonus":"only one field"}',
     '{"welcome_bonus":"x","wagering_requirement_multiplier":4,"minimum_deposit":"R5"}'],
)
def test_invalid_structured_response_is_rejected(response_text: str | None) -> None:
    models = FakeModels(response_text)
    with pytest.raises(gemini_client.GeminiResponseError):
        gemini_client.extract_bonus_terms(
            "Synthetic offer terms", client=FakeClient(models)  # type: ignore[arg-type]
        )


def test_api_error_is_wrapped_without_raw_error_details(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeAPIError(Exception):
        pass

    monkeypatch.setattr(gemini_client.errors, "APIError", FakeAPIError)
    models = FakeModels(error=FakeAPIError("credential-bearing details must not be surfaced"))

    with pytest.raises(gemini_client.GeminiRequestError) as raised:
        gemini_client.extract_bonus_terms(
            "Synthetic offer terms", client=FakeClient(models)  # type: ignore[arg-type]
        )

    assert "credential-bearing" not in str(raised.value)


def test_empty_input_is_rejected_before_api_call() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        gemini_client.extract_bonus_terms("  ", client=FakeClient(FakeModels()))  # type: ignore[arg-type]


@pytest.mark.skipif(
    not gemini_client.is_configured(),
    reason="Live synthetic diagnostic pending local GEMINI_API_KEY configuration",
)
def test_synthetic_gemini_diagnostic() -> None:
    """Uses synthetic text only; this is not casino scraping evidence."""
    synthetic_terms = (
        "Synthetic diagnostic only: receive a 100% first-deposit match up to R2,000. "
        "The casino bonus must be wagered 10 times before withdrawal. "
        "Minimum qualifying deposit: R50."
    )

    result = gemini_client.extract_bonus_terms(synthetic_terms)

    assert "100%" in result["welcome_bonus"]
    assert "10" in result["wagering_requirement_multiplier"]
    assert "R50" in result["minimum_deposit"]
