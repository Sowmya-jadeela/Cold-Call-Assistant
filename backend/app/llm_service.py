import os
from pathlib import Path

import requests
from dotenv import load_dotenv


# Load backend/.env regardless of the terminal's working directory.
BACKEND_DIR = Path(__file__).resolve().parents[1]
ENV_FILE = BACKEND_DIR / ".env"

load_dotenv(dotenv_path=ENV_FILE, override=True)


def get_coaching(
    stage_number: int,
    stage_name: str,
    prospect_words: str = "",
    notes: str = "",
) -> str:
    """Generate practical cold-call coaching using Gemini."""

    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    model = os.getenv("GEMINI_MODEL", "gemini-3.8-flash").strip()

    # Provide a useful fallback if no key is configured.
    if not api_key:
        return (
            f"Stage {stage_number}: {stage_name}\n\n"
            "Suggested response: Acknowledge what the prospect said, "
            "respect their time, and ask one clear follow-up question.\n\n"
            "Live AI coaching is unavailable because GEMINI_API_KEY "
            "is not configured in backend/.env."
        )

    if not model:
        raise RuntimeError(
            "GEMINI_MODEL is empty. Configure it in backend/.env."
        )

    prompt = f"""
You are a practical, respectful cold-call coach.

Current stage: {stage_number} - {stage_name}
Prospect's exact words: {prospect_words or "Not provided"}
Caller notes: {notes or "None"}

Give the caller:
1. Interpretation: briefly explain what the prospect may mean.
2. Suggested response: provide one natural sentence to say next.
3. Follow-up question: suggest one useful question.
4. Avoid: identify one thing the caller should avoid.

Keep the advice concise, ethical, conversational, and pressure-free.
Do not invent facts about the prospect or promise unsupported results.
If the prospect declines, respect their decision.
"""

    url = (
        "https://generativelanguage.googleapis.com/"
        f"v1beta/models/{model}:generateContent"
    )

    request_body = {
        "system_instruction": {
            "parts": [
                {
                    "text": (
                        "You are a helpful, ethical sales conversation coach. "
                        "Give clear, practical, concise coaching."
                    )
                }
            ]
        },
        "contents": [
            {
                "role": "user",
                "parts": [{"text": prompt}],
            }
        ],
        "generationConfig": {
            "maxOutputTokens": 500,
        },
    }

    try:
        response = requests.post(
            url,
            headers={
                "x-goog-api-key": api_key,
                "Content-Type": "application/json",
            },
            json=request_body,
            timeout=30,
        )
    except requests.Timeout as exc:
        raise RuntimeError(
            "Gemini request timed out. Please try again."
        ) from exc
    except requests.RequestException as exc:
        raise RuntimeError(
            f"Could not connect to Gemini: {exc}"
        ) from exc

    try:
        data = response.json()
    except ValueError:
        data = {}

    if not isinstance(data, dict):
        data = {}

    # Return useful error messages instead of silently failing.
    if not response.ok:
        error = data.get("error") or {}
        message = error.get("message") or response.text[:300]

        if response.status_code in (401, 403):
            raise RuntimeError(
                "Gemini rejected the API key or denied access. "
                "Check GEMINI_API_KEY and the project's API access."
            )

        if response.status_code == 404:
            raise RuntimeError(
                f"Gemini model '{model}' was not found or is unavailable. "
                "Check GEMINI_MODEL in backend/.env."
            )

        if response.status_code == 429:
            raise RuntimeError(
                "Gemini quota or rate limit reached. Check your "
                "Google AI Studio quota and billing settings."
            )

        raise RuntimeError(
            f"Gemini API returned HTTP {response.status_code}: {message}"
        )

    candidates = data.get("candidates") or []

    if not candidates:
        feedback = data.get("promptFeedback") or {}
        reason = feedback.get("blockReason")

        if reason:
            raise RuntimeError(
                f"Gemini did not generate a response: {reason}."
            )

        raise RuntimeError(
            "Gemini returned no response candidates."
        )

    candidate = candidates[0] or {}
    content = candidate.get("content") or {}
    parts = content.get("parts") or []

    text_parts = [
        part["text"].strip()
        for part in parts
        if isinstance(part, dict)
        and isinstance(part.get("text"), str)
        and part["text"].strip()
    ]

    answer = "\n".join(text_parts).strip()

    if not answer:
        reason = candidate.get("finishReason", "unknown")
        raise RuntimeError(
            f"Gemini returned an empty response. Finish reason: {reason}."
        )

    return answer