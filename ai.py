"""
ai.py — thin wrapper around Google Gemini (free tier) for:
  1) Answering group members' questions (text)
  2) Classifying photos/videos (via first frame) as appropriate/inappropriate

Get a free API key at https://aistudio.google.com/apikey and set it as the
GEMINI_API_KEY environment variable.
"""

import os
import google.generativeai as genai

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
genai.configure(api_key=GEMINI_API_KEY)

TEXT_MODEL = "gemini-2.5-flash"
VISION_MODEL = "gemini-2.5-flash"

QA_SYSTEM_PROMPT = (
    "You are a helpful assistant inside a Telegram group chat where members "
    "often write in Banglish (Bengali written with English letters), mixed "
    "with English and Bengali script. Understand Banglish naturally. Reply "
    "concisely (a few sentences max unless asked for detail), in the same "
    "language style the user asked in (Bangli
)

MODERATION_PROMPT = (
    "You are a content moderator for a family-friendly Telegram group. "
    "Look at this image and decide if it is inappropriate for a general "
    "audience (e.g. nudity, sexual content, gore, graphic violence). "
    "Reply with exactly one word: SAFE or UNSAFE."
)


def ask_ai(question: str) -> str:
    if not GEMINI_API_KEY:
        return "AI isn't configured yet — ask the group admin to set GEMINI_API_KEY."
    model = genai.GenerativeModel(TEXT_MODEL, system_instruction=QA_SYSTEM_PROMPT)
    try:
        resp = model.generate_content(question)
        return (resp.text or "").strip() or "Sorry, I couldn't come up with an answer."
    except Exception as e:
        return f"AI error: {e}"


def is_image_unsafe(image_bytes: bytes, mime_type: str = "image/jpeg") -> bool:
    """Returns True if the image should be deleted."""
    if not GEMINI_API_KEY:
        return False  # fail open — don't delete content if AI isn't configured
    model = genai.GenerativeModel(VISION_MODEL)
    try:
        resp = model.generate_content(
            [
                MODERATION_PROMPT,
                {"mime_type": mime_type, "data": image_bytes},
            ]
        )
        verdict = (resp.text or "").strip().upper()
        return "UNSAFE" in verdict
    except Exception:
        return False  # fail open on API errors
