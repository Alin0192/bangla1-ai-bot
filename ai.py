"""
ai.py — thin wrapper around Google Gemini (free tier) for:
  1) Answering group members' questions (text)
  2) Classifying photos/videos (via first frame) as appropriate/inappropriate

Get a free API key at https://aistudio.google.com/apikey and set it as the
GEMINI_API_KEY environment variable.

Uses Google's current "google-genai" SDK (the older "google-generativeai"
package is deprecated). Model names use the "-latest" alias so this keeps
working automatically as Google upgrades its models, instead of needing a
code update every time a specific model version gets retired.
"""

import os
from google import genai
from google.genai import types

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
_client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

TEXT_MODEL = "gemini-flash-latest"
VISION_MODEL = "gemini-flash-latest"

QA_SYSTEM_PROMPT = (
    "You are a helpful assistant inside a Telegram group chat where members "
    "often write in Banglish (Bengali written with English letters), mixed "
    "with English and Bengali script. Understand Banglish naturally. Reply "
    "concisely (a few sentences max unless asked for detail), in the same "
    "language style the user asked in (Banglish/English/Bengali)."
)

MODERATION_PROMPT = (
    "You are a content moderator for a family-friendly Telegram group. "
    "Look at this image and decide if it is inappropriate for a general "
    "audience (e.g. nudity, sexual content, gore, graphic violence). "
    "Reply with exactly one word: SAFE or UNSAFE."
)


def ask_ai(question: str) -> str:
    if not _client:
        return "AI isn't configured yet — ask the group admin to set GEMINI_API_KEY."
    try:
        resp = _client.models.generate_content(
            model=TEXT_MODEL,
            contents=question,
            config=types.GenerateContentConfig(system_instruction=QA_SYSTEM_PROMPT),
        )
        return (resp.text or "").strip() or "Sorry, I couldn't come up with an answer."
    except Exception as e:
        return f"AI error: {e}"


def is_image_unsafe(image_bytes: bytes, mime_type: str = "image/jpeg") -> bool:
    """Returns True if the image should be deleted."""
    if not _client:
        return False  # fail open — don't delete content if AI isn't configured
    try:
        resp = _client.models.generate_content(
            model=VISION_MODEL,
            contents=[
                MODERATION_PROMPT,
                types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
            ],
        )
        verdict = (resp.text or "").strip().upper()
        return "UNSAFE" in verdict
    except Exception:
        return False  # fail open on API errors
