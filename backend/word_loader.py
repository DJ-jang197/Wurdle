"""Load and validate words from dictionary files."""

import os
from functools import lru_cache

WORD_LISTS_DIR = os.path.join(os.path.dirname(__file__), "word_lists")
VALID_GUESSES_PATH = os.path.join(WORD_LISTS_DIR, "valid_guesses.txt")
ANSWERS_PATH = os.path.join(WORD_LISTS_DIR, "answers.txt")


def reload_word_lists() -> None:
    """Clear cached word lists (useful after regenerating files)."""
    _load_word_set.cache_clear()


@lru_cache(maxsize=1)
def _load_word_set(path: str) -> frozenset[str]:
    with open(path, encoding="utf-8") as f:
        return frozenset(line.strip().lower() for line in f if line.strip())


def get_valid_guesses() -> frozenset[str]:
    return _load_word_set(VALID_GUESSES_PATH)


def get_answers() -> frozenset[str]:
    return _load_word_set(ANSWERS_PATH)


def is_valid_guess(word: str) -> bool:
    """Return True if word is a valid 5-letter guess (case-insensitive)."""
    normalized = word.strip().lower()
    if len(normalized) != 5 or not normalized.isalpha():
        return False
    return normalized in get_valid_guesses()


def pick_random_answer() -> str:
    import random

    from practice_chain import get_mutable_answers

    pool = list(get_mutable_answers())
    if not pool:
        pool = list(get_answers())
    return random.choice(pool)
