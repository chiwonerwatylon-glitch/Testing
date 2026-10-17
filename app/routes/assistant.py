from __future__ import annotations

from http import HTTPStatus
from typing import Any, Dict, Optional, Tuple

from flask import Blueprint, jsonify, render_template, request
from flask_login import login_required

from app.utils.decorators import active_user_required
from app.utils.fml_website import get_fml_website_text
from app.utils.gemini import ask_gemini, GeminiError
from app.utils.system_context import SYSTEM_CONTEXT


assistant_bp = Blueprint("assistant", __name__, url_prefix="/assistant")

MAX_QUESTION_LENGTH: int = 1000
UNAVAILABLE_MESSAGE: str = "The assistant is unavailable right now."
ERROR_INVALID_QUESTION: str = "Please enter a question."
ERROR_TOO_LONG: str = f"Question must be {MAX_QUESTION_LENGTH} characters or fewer."
DEFAULT_SOURCES = ["requisition system documentation"]


def _parse_request_json() -> Tuple[Optional[str], Optional[Tuple[Dict[str, Any], int]]]:
    """
    Safely parse the JSON body and extract the 'question' field.

    Returns:
        (question, error_response)
        - question: the stripped question string if valid, otherwise None
        - error_response: a tuple (json_body, status_code) if an error occurs,
          otherwise None
    """
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return None, ({"error": ERROR_INVALID_QUESTION}, HTTPStatus.BAD_REQUEST)

    question = data.get("question")

    if not isinstance(question, str) or not question.strip():
        return None, ({"error": ERROR_INVALID_QUESTION}, HTTPStatus.BAD_REQUEST)

    question = question.strip()
    if len(question) > MAX_QUESTION_LENGTH:
        return None, ({"error": ERROR_TOO_LONG}, HTTPStatus.BAD_REQUEST)

    return question, None


@assistant_bp.route("/")
@login_required
@active_user_required
def index():
    """Render the assistant page."""
    return render_template("assistant.html")


@assistant_bp.route("/ask", methods=["POST"])
@login_required
@active_user_required
def ask():
    """Handle assistant questions via JSON POST payload."""
    question, error_response = _parse_request_json()
    if error_response is not None:
        body, status = error_response
        return jsonify(body), status

    # At this point question is guaranteed to be a non-empty, trimmed string
    assert question is not None

    site_text = get_fml_website_text()

    try:
        answer = ask_gemini(question, SYSTEM_CONTEXT, site_text)
    except (GeminiError, RuntimeError):
        return (
            jsonify({"error": UNAVAILABLE_MESSAGE}),
            HTTPStatus.SERVICE_UNAVAILABLE,
        )

    sources = list(DEFAULT_SOURCES)
    if site_text:
        sources.append("FML website")

    return jsonify({"answer": answer, "sources": sources}), HTTPStatus.OK
