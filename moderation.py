"""
moderation.py — spam detection + Banglish/Bangla profanity filter.

BAD WORDS FILE
--------------
Real curse words are intentionally NOT hard-coded in this file — you know your
group's slang better than a generic list would. Put one word per line (plain,
lowercase, no symbols) in `bad_words.txt` next to this file. The matcher
below automatically catches common obfuscations like "c##", "c_h_u_d_a",
"ch*da", extra repeated letters, etc., so you don't need to list every
variant — just the base/root word.

Example bad_words.txt (replace with your own list):
    magi
    khankir
    chuda
    boka  <- (harmless placeholder, delete this line)
"""

import re
import time
from pathlib import Path

BAD_WORDS_FILE = Path(__file__).parent / "bad_words.txt"

# --- link / spam heuristics ---
URL_RE = re.compile(r"(https?://|t\.me/|www\.|\.com\b|\.net\b|\.io\b)", re.IGNORECASE)
MENTION_RE = re.compile(r"@\w{4,}")

# Flood control
FLOOD_WINDOW_SECONDS = 10
FLOOD_MAX_MESSAGES = 6      # more than this many messages in the window = spam
LINK_MAX_PER_MSG = 3        # more than this many links in one message = spam


def _load_bad_words():
    if not BAD_WORDS_FILE.exists():
        BAD_WORDS_FILE.write_text(
            "# Add one root word per line (lowercase, no spaces/symbols).\n"
            "# The bot automatically catches spaced-out / symbol-obfuscated\n"
            "# variants (e.g. 'c##', 'c-h-u-d-a') of whatever you list here.\n"
            "# Lines starting with # are ignored.\n"
        )
    words = []
    for line in BAD_WORDS_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip().lower()
        if line and not line.startswith("#"):
            words.append(line)
    return words


def _build_pattern(word: str) -> re.Pattern:
    # Allow any non-letter junk (#, *, _, -, ., spaces, digits) between each
    # letter so obfuscated spellings still match the root word.
    fuzzy = r"[\W\d_]*".join(re.escape(ch) for ch in word)
    return re.compile(fuzzy, re.IGNORECASE)


_BAD_PATTERNS = None


def _patterns():
    global _BAD_PATTERNS
    if _BAD_PATTERNS is None:
        _BAD_PATTERNS = [(w, _build_pattern(w)) for w in _load_bad_words()]
    return _BAD_PATTERNS


def reload_bad_words():
    """Call this if you edit bad_words.txt while the bot is running."""
    global _BAD_PATTERNS
    _BAD_PATTERNS = None


def contains_bad_word(text: str) -> str | None:
    """Return the matched root word if text contains profanity, else None."""
    if not text:
        return None
    normalized = text.lower()
    for word, pattern in _patterns():
        if pattern.search(normalized):
            return word
    return None


QUESTION_WORDS = {
    # English
    "what", "why", "how", "when", "where", "who", "which", "whose",
    "is", "are", "was", "were", "do", "does", "did", "can", "could",
    "would", "will", "should", "may",
    # Banglish (Bengali written in Latin letters)
    "ki", "kn", "keno", "kano", "kivabe", "kibhabe", "kemne", "kokhon",
    "kobe", "kothay", "kothae", "ke", "kar", "kader", "koto", "kotota",
    "naki", "acho", "achen", "korbe", "korba", "korish", "korbi",
}

# Bengali-script question words
BANGLA_QUESTION_WORDS = {"কি", "কেন", "কিভাবে", "কবে", "কোথায়", "কে", "কার", "কত"}


def looks_like_question(text: str) -> bool:
    if not text:
        return False
    stripped = text.strip()
    if stripped.endswith("?") or stripped.endswith("؟"):
        return True
    words = re.findall(r"[a-zA-Z\u0980-\u09FF]+", stripped.lower())
    if not words:
        return False
    first_word = words[0]
    if first_word in QUESTION_WORDS or first_word in BANGLA_QUESTION_WORDS:
        return True
    return any(w in BANGLA_QUESTION_WORDS for w in words)


def is_spammy_text(text: str) -> bool:
    if not text:
        return False
    links = URL_RE.findall(text)
    mentions = MENTION_RE.findall(text)
    if len(links) >= LINK_MAX_PER_MSG:
        return True
    if len(links) >= 1 and len(mentions) >= 2:
        return True
    return False
