from flask import Blueprint, jsonify, render_template, request
from flask_login import login_required
from app.utils.decorators import active_user_required
from app.utils.fml_website import get_fml_website_text
from app.utils.gemini import ask_gemini, GeminiError
from app.utils.system_context import SYSTEM_CONTEXT

assistant_bp = Blueprint('assistant', __name__, url_prefix='/assistant')

MAX_QUESTION_LENGTH = 1000
UNAVAILABLE_MESSAGE = 'The assistant is unavailable right now.'


@assistant_bp.route('/')
@login_required
@active_user_required
def index():
    return render_template('assistant.html')


@assistant_bp.route('/ask', methods=['POST'])
@login_required
@active_user_required
def ask():
    data = request.get_json(silent=True)
    question = data.get('question') if isinstance(data, dict) else None
    if not isinstance(question, str) or not question.strip():
        return jsonify({'error': 'Please enter a question.'}), 400
    question = question.strip()
    if len(question) > MAX_QUESTION_LENGTH:
        return jsonify({'error': f'Question must be {MAX_QUESTION_LENGTH} characters or fewer.'}), 400

    site_text = get_fml_website_text()
    try:
        answer = ask_gemini(question, SYSTEM_CONTEXT, site_text)
    except (GeminiError, RuntimeError):
        return jsonify({'error': UNAVAILABLE_MESSAGE}), 503

    sources = ['requisition system documentation']
    if site_text:
        sources.append('FML website')
    return jsonify({'answer': answer, 'sources': sources})
