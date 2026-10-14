"""Small local-only client for schema-constrained Gemini bonus extraction."""

from __future__ import annotations

import json
import os
from typing import Any

from dotenv import load_dotenv
from google import genai
from google.genai import errors, types

MODEL_ID = "gemini-3.5-flash-lite"

BONUS_TERMS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "welcome_bonus": {
            "type": "string",
            "description": "The published welcome offer. Use an empty string if not stated.",
        },
        "wagering_requirement_multiplier": {
            "type": "string",
            "description": (
                "Preserve every multiplier and its category verbatim (for example, "
                "sports, casino, free bet, or spins). Never merge different categories. "
                "Use an empty string if not stated."
            ),
        },
        "minimum_deposit": {
            "type": "string",
            "description": "The stated qualifying minimum deposit, including currency. Use an empty string if absent.",
        },
    },
    "required": [
        "welcome_bonus",
        "wagering_requirement_multiplier",
        "minimum_deposit",
    ],
    "additionalProperties": False,
}


class GeminiConfigurationError(RuntimeError):
    """Raised when the local Gemini API key is not configured."""


class GeminiRequestError(RuntimeError):
    """Raised when Gemini rejects or cannot complete a request."""


class GeminiResponseError(RuntimeError):
    """Raised when a response is not valid structured bonus data."""


def is_configured() -> bool:
    """Return whether GEMINI_API_KEY is available without exposing its value."""
    load_dotenv(override=False)
    return bool(os.getenv("GEMINI_API_KEY", "").strip())


def _client_from_environment() -> genai.Client:
    load_dotenv(override=False)
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise GeminiConfigurationError(
            "GEMINI_API_KEY is not configured; set it locally before calling Gemini."
        )
    return genai.Client(api_key=api_key)


def _validate_response(text: str | None) -> dict[str, str]:
    if not text:
        raise GeminiResponseError("Gemini returned no structured response text.")

    try:
        payload = json.loads(text)
    except (json.JSONDecodeError, TypeError) as exc:
        raise GeminiResponseError("Gemini returned invalid JSON.") from exc

    if not isinstance(payload, dict):
        raise GeminiResponseError("Gemini response must be a JSON object.")

    expected = set(BONUS_TERMS_SCHEMA["required"])
    if set(payload) != expected:
        raise GeminiResponseError("Gemini response fields do not match the required schema.")
    if any(not isinstance(payload[field], str) for field in expected):
        raise GeminiResponseError("All extracted bonus fields must be strings.")

    return {field: payload[field] for field in BONUS_TERMS_SCHEMA["required"]}


def extract_bonus_terms(
    free_text: str,
    *,
    client: genai.Client | None = None,
    model: str = MODEL_ID,
) -> dict[str, str]:
    """Extract three fields from source text, preserving separate wager categories."""
    if not isinstance(free_text, str) or not free_text.strip():
        raise ValueError("free_text must be a non-empty string")

    gemini = client if client is not None else _client_from_environment()
    prompt = (
        "Extract only facts explicitly present in the promotional text below. "
        "Do not infer missing values. Keep sports, casino, free-bet, and free-spin "
        "wagering requirements distinct and include their labels in the multiplier field.\n\n"
        f"Promotional text:\n{free_text.strip()}"
    )

    try:
        response = gemini.models.generate_content(
            model=model,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_json_schema=BONUS_TERMS_SCHEMA,
                temperature=0,
            ),
        )
    except errors.APIError as exc:
        # Avoid logging raw request/response details or any credential-bearing data.
        raise GeminiRequestError(
            f"Gemini API request failed ({type(exc).__name__}); check model access, quota, and connectivity."
        ) from exc

    return _validate_response(response.text)
