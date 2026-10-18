from __future__ import annotations

import logging
import os
import sqlite3
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #

GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
)
DEFAULT_MODEL = "gemini-2.5-flash"
REQUEST_TIMEOUT = 30
SEARCH_TIMEOUT = 45  # grounded (web search) calls can take a bit longer

KNOWLEDGE_DB_PATH = os.environ.get(
    "GEMINI_KNOWLEDGE_DB",
    os.path.join(os.getcwd(), "data", "gemini_knowledge.db"),
)
KNOWLEDGE_MAX_AGE_HOURS = float(os.environ.get("GEMINI_KNOWLEDGE_MAX_AGE_HOURS", "24"))
REFRESH_INTERVAL_SECONDS = 24 * 60 * 60

# Topics the assistant keeps itself up to date on, daily, via Google Search
# grounding. Feel free to extend this list.
DEFAULT_TOPICS: Dict[str, str] = {
    "fml_overview": (
        "First Mutual Life Assurance Company Zimbabwe: latest public information "
        "about its products, services, leadership, contact details and any recent "
        "news or announcements."
    ),
    "ipec_statutory": (
        "Insurance and Pensions Commission (IPEC) Zimbabwe: current statutory and "
        "regulatory requirements for life assurance companies, including "
        "compliance, reporting, capital adequacy, policyholder protection and "
        "any recent directives or circulars."
    ),
}

SYSTEM_PROMPT = (
    "You are the First Mutual Life Assurance Company requisition system assistant, "
    "operating at a senior, professional analyst level.\n\n"
    "You must ground every answer in, and prefer, the following sources in this "
    "order of priority:\n"
    "1. SYSTEM CONTEXT / LIVE SYSTEM DATA — real data currently stored in this "
    "requisition system (requisitions, approvals, users, configuration, etc.).\n"
    "2. FML WEBSITE CONTEXT — content sourced from First Mutual Life's own "
    "website or materials.\n"
    "3. KNOWLEDGE BASE (auto-refreshed daily) — cached public information about "
    "First Mutual Life and IPEC statutory/regulatory requirements.\n"
    "4. Live Google Search (when the google_search tool is available to you) — "
    "use this only to fill genuine gaps about First Mutual Life as a public "
    "company or about IPEC (Insurance and Pensions Commission of Zimbabwe) "
    "statutory requirements. Clearly indicate when information came from a web "
    "search, and list sources if available.\n\n"
    "Never invent figures, policy numbers, contacts, approval statuses or dates. "
    "If the answer genuinely cannot be found in any of the above, say so plainly "
    "and recommend the user contact First Mutual Life directly. Be concise, "
    "accurate, and professional."
)


class GeminiError(Exception):
    """Raised when the Gemini request fails. The message is safe to show to users."""


# --------------------------------------------------------------------------- #
# Knowledge store (daily-refreshed cache + interaction log)
# --------------------------------------------------------------------------- #


class KnowledgeStore:
    """A tiny SQLite-backed cache of daily knowledge and a log of Q&A history.

    This is not machine learning — it's a simple, transparent cache + audit log
    that lets the assistant "remember" what it looked up recently instead of
    re-searching the web on every request, and gives admins a record of what
    has been asked/answered.
    """

    def __init__(self, db_path: str = KNOWLEDGE_DB_PATH) -> None:
        self.db_path = db_path
        os.makedirs(os.path.dirname(self.db_path) or ".", exist_ok=True)
        self._init_db()

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(self.db_path, timeout=10)
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS knowledge (
                    topic TEXT PRIMARY KEY,
                    content TEXT NOT NULL,
                    sources TEXT,
                    fetched_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS interactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    question TEXT NOT NULL,
                    answer TEXT NOT NULL,
                    used_web_search INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL
                )
                """
            )

    # -- knowledge cache -------------------------------------------------- #

    def get(self, topic: str) -> Optional[Dict[str, str]]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT content, sources, fetched_at FROM knowledge WHERE topic = ?",
                (topic,),
            ).fetchone()
        if not row:
            return None
        content, sources, fetched_at = row
        return {"content": content, "sources": sources or "", "fetched_at": fetched_at}

    def needs_refresh(self, topic: str, max_age_hours: float = KNOWLEDGE_MAX_AGE_HOURS) -> bool:
        entry = self.get(topic)
        if not entry:
            return True
        try:
            fetched_at = datetime.fromisoformat(entry["fetched_at"])
        except ValueError:
            return True
        age_hours = (datetime.now(timezone.utc) - fetched_at).total_seconds() / 3600
        return age_hours >= max_age_hours

    def save(self, topic: str, content: str, sources: str = "") -> None:
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO knowledge (topic, content, sources, fetched_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(topic) DO UPDATE SET
                    content = excluded.content,
                    sources = excluded.sources,
                    fetched_at = excluded.fetched_at
                """,
                (topic, content, sources, datetime.now(timezone.utc).isoformat()),
            )

    def all_knowledge_text(self) -> str:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT topic, content, fetched_at FROM knowledge ORDER BY topic"
            ).fetchall()
        if not rows:
            return "(no cached knowledge yet)"
        chunks = []
        for topic, content, fetched_at in rows:
            chunks.append(f"[{topic}] (as of {fetched_at})\n{content}")
        return "\n\n".join(chunks)

    # -- interaction log ---------------------------------------------------- #

    def log_interaction(self, question: str, answer: str, used_web_search: bool) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO interactions (question, answer, used_web_search, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (question, answer, int(used_web_search), datetime.now(timezone.utc).isoformat()),
            )

    def recent_interactions(self, limit: int = 20) -> List[Dict[str, Any]]:
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT question, answer, used_web_search, created_at
                FROM interactions ORDER BY id DESC LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [
            {
                "question": q,
                "answer": a,
                "used_web_search": bool(w),
                "created_at": c,
            }
            for q, a, w, c in rows
        ]


_knowledge_store = KnowledgeStore()

# Optional hook: the host app can register a callable that returns a string
# snapshot of "live system data" (recent requisitions, counts, statuses, etc.)
# so the assistant can answer questions about what's actually in the system.
_system_data_provider: Optional[Callable[[], str]] = None


def register_system_data_provider(provider: Callable[[], str]) -> None:
    """Register a callable returning a text snapshot of live system data.

    Call this once at app start-up, e.g.:

        def system_snapshot() -> str:
            return (
                f"Total requisitions: {Requisition.query.count()}\n"
                f"Pending approval: {Requisition.query.filter_by(status='pending').count()}\n"
                ...
            )

        register_system_data_provider(system_snapshot)
    """
    global _system_data_provider
    _system_data_provider = provider


def _get_live_system_context() -> str:
    if _system_data_provider is None:
        return ""
    try:
        return _system_data_provider() or ""
    except Exception:  # pragma: no cover - defensive, provider is host app code
        logger.exception("System data provider raised an exception.")
        return ""


# --------------------------------------------------------------------------- #
# Low-level Gemini call
# --------------------------------------------------------------------------- #


def _call_gemini(
    body: Dict[str, Any],
    *,
    timeout: int = REQUEST_TIMEOUT,
    model: Optional[str] = None,
) -> Dict[str, Any]:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not configured.")

    model = model or os.environ.get("GEMINI_MODEL") or DEFAULT_MODEL

    try:
        response = requests.post(
            GEMINI_URL.format(model=model),
            headers={
                "x-goog-api-key": api_key,
                "Content-Type": "application/json",
            },
            json=body,
            timeout=timeout,
        )
        response.raise_for_status()
        return response.json()
    except requests.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else "unknown"
        logger.warning("Gemini request failed with HTTP status %s", status)
        raise GeminiError("The Gemini service returned an error.") from None
    except (requests.RequestException, ValueError):
        logger.warning("Gemini request failed.")
        raise GeminiError("Could not reach the Gemini service.") from None


def _extract_text_and_sources(data: Dict[str, Any]) -> tuple[str, List[str]]:
    try:
        candidate = (data.get("candidates") or [])[0]
        parts = candidate["content"]["parts"]
        text = "".join(part.get("text", "") for part in parts).strip()
    except (KeyError, IndexError, TypeError, AttributeError):
        logger.warning("Gemini response could not be parsed.")
        raise GeminiError("Unexpected response from the Gemini service.") from None

    sources: List[str] = []
    grounding = (candidate or {}).get("groundingMetadata") or {}
    for chunk in grounding.get("groundingChunks", []) or []:
        web = chunk.get("web") or {}
        uri = web.get("uri")
        title = web.get("title") or uri
        if uri and title:
            sources.append(f"{title} ({uri})")

    return text, sources


# --------------------------------------------------------------------------- #
# Daily knowledge refresh (Google-Search-grounded)
# --------------------------------------------------------------------------- #


def _fetch_grounded_topic(topic_prompt: str) -> tuple[str, List[str]]:
    """Ask Gemini, with Google Search grounding enabled, about a topic."""
    body: Dict[str, Any] = {
        "system_instruction": {
            "parts": [
                {
                    "text": (
                        "You are a research assistant. Using Google Search, find "
                        "accurate, current, and well-sourced information. Be factual "
                        "and concise, and do not fabricate details."
                    )
                }
            ]
        },
        "contents": [{"role": "user", "parts": [{"text": topic_prompt}]}],
        "tools": [{"google_search": {}}],
        "generationConfig": {"temperature": 0.1, "maxOutputTokens": 1024},
    }
    data = _call_gemini(body, timeout=SEARCH_TIMEOUT)
    return _extract_text_and_sources(data)


def refresh_daily_knowledge(force: bool = False, topics: Optional[Dict[str, str]] = None) -> None:
    """Refresh the cached knowledge base for each topic if it's stale (or forced).

    Safe to call repeatedly (e.g. from a scheduler or cron); it only hits the
    API for topics that actually need refreshing unless force=True.
    """
    topics = topics or DEFAULT_TOPICS
    for topic, prompt in topics.items():
        if not force and not _knowledge_store.needs_refresh(topic):
            continue
        try:
            text, sources = _fetch_grounded_topic(prompt)
            _knowledge_store.save(topic, text, "; ".join(sources))
            logger.info("Refreshed knowledge topic '%s' (%d sources).", topic, len(sources))
        except GeminiError as exc:
            logger.warning("Could not refresh knowledge topic '%s': %s", topic, exc)
        except RuntimeError:
            # GEMINI_API_KEY not configured — nothing we can do.
            logger.warning("Skipping knowledge refresh: GEMINI_API_KEY not configured.")
            return


_refresh_thread_started = False
_refresh_thread_lock = threading.Lock()


def start_background_refresh(interval_seconds: int = REFRESH_INTERVAL_SECONDS) -> None:
    """Start a daemon thread that refreshes the knowledge base once a day.

    Call this once from your app's start-up code (e.g. in the app factory),
    after the environment / config has been loaded. Idempotent — safe to call
    more than once.
    """
    global _refresh_thread_started
    with _refresh_thread_lock:
        if _refresh_thread_started:
            return
        _refresh_thread_started = True

    def _loop() -> None:
        while True:
            try:
                refresh_daily_knowledge()
            except Exception:  # pragma: no cover - never let the thread die silently
                logger.exception("Daily knowledge refresh failed unexpectedly.")
            time.sleep(interval_seconds)

    thread = threading.Thread(target=_loop, name="gemini-knowledge-refresh", daemon=True)
    thread.start()
    logger.info("Started background Gemini knowledge refresh thread.")


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #


def ask_gemini(
    question: str,
    system_context: str | None = None,
    site_context: str | None = None,
    *,
    use_web_grounding: bool = True,
    include_sources: bool = True,
) -> str:
    """Ask Gemini a question grounded in the given contexts and return the answer text.

    Fully backward compatible with the previous signature
    (`ask_gemini(question, system_context, site_context)`), with optional
    extras:

    - Automatically merges in any live system data registered via
      `register_system_data_provider`.
    - Automatically merges in the daily-refreshed knowledge base about First
      Mutual Life and IPEC statutory requirements.
    - Optionally enables live Google Search grounding for the current question
      (on top of the daily cache), so niche or very recent questions can still
      be answered.
    - Logs the interaction for audit purposes.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not configured.")

    live_system_data = _get_live_system_context()
    merged_system_context = "\n\n".join(
        part for part in [system_context, live_system_data] if part
    ) or "(none)"

    knowledge_base = _knowledge_store.all_knowledge_text()

    instruction = (
        f"{SYSTEM_PROMPT}\n\n"
        f"SYSTEM CONTEXT / LIVE SYSTEM DATA:\n{merged_system_context}\n\n"
        f"FML WEBSITE CONTEXT:\n{site_context or '(none)'}\n\n"
        f"KNOWLEDGE BASE (auto-refreshed daily, about First Mutual Life and "
        f"IPEC statutory requirements):\n{knowledge_base}"
    )

    body: Dict[str, Any] = {
        "system_instruction": {"parts": [{"text": instruction}]},
        "contents": [{"role": "user", "parts": [{"text": question}]}],
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 1024},
    }
    if use_web_grounding:
        body["tools"] = [{"google_search": {}}]

    timeout = SEARCH_TIMEOUT if use_web_grounding else REQUEST_TIMEOUT
    data = _call_gemini(body, timeout=timeout)
    text, sources = _extract_text_and_sources(data)

    if not text:
        raise GeminiError("The Gemini service returned an empty answer.")

    if include_sources and sources:
        text = f"{text}\n\nSources:\n" + "\n".join(f"- {s}" for s in sources)

    try:
        _knowledge_store.log_interaction(question, text, used_web_search=bool(sources))
    except Exception:  # pragma: no cover - logging must never break the response
        logger.exception("Failed to log Gemini interaction.")

    return text
