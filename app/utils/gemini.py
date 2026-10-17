from __future__ import annotations

import logging
import os
from typing import Any, Dict

import requests

logger = logging.getLogger(__name__)

GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
)
DEFAULT_MODEL = "gemini-2.5-flash"
REQUEST_TIMEOUT = 30

SYSTEM_PROMPT = (
    "You are the First Mutual Life Assurance Company requisition system assistant. "
    "Answer only from the SYSTEM CONTEXT and FML WEBSITE CONTEXT given below. "
    "If the answer is not there, say so and suggest contacting First Mutual Life directly. "
    "Do not invent figures, policies or contacts. Be concise."
)


class GeminiError(Exception):
    """Raised when the Gemini request fails. The message is safe to show to users."""


def ask_gemini(question: str, system_context: str | None, site_context: str | None) -> str:
    """Ask Gemini a question grounded in the given contexts and return the answer text."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not configured.")

    model = os.environ.get("GEMINI_MODEL") or DEFAULT_MODEL
    instruction = (
        f"{SYSTEM_PROMPT}\n\n"
        f"SYSTEM CONTEXT:\n{system_context or '(none)'}\n\n"
        f"FML WEBSITE CONTEXT:\n{site_context or '(none)'}"
    )

    body: Dict[str, Any] = {
        "system_instruction": {"parts": [{"text": instruction}]},
        "contents": [{"role": "user", "parts": [{"text": question}]}],
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 1024},
    }

    try:
        response = requests.post(
            GEMINI_URL.format(model=model),
            headers={
                "x-goog-api-key": api_key,
                "Content-Type": "application/json",
            },
            json=body,
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()
    except requests.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else "unknown"
        logger.warning("Gemini request failed with HTTP status %s", status)
        raise GeminiError("The Gemini service returned an error.") from None
    except (requests.RequestException, ValueError):
        logger.warning("Gemini request failed.")
        raise GeminiError("Could not reach the Gemini service.") from None

    try:
        candidates = data.get("candidates") or []
        parts = candidates[0]["content"]["parts"]
        text = "".join(part.get("text", "") for part in parts).strip()
    except (KeyError, IndexError, TypeError, AttributeError):
        logger.warning("Gemini response could not be parsed.")
        raise GeminiError("Unexpected response from the Gemini service.") from None

    if not text:
        raise GeminiError("The Gemini service returned an empty answer.")

    return text
