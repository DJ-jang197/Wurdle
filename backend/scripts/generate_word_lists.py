"""Regenerate word lists from ENABLE + common English words."""

import os
import urllib.request

WORD_LISTS_DIR = os.path.join(os.path.dirname(__file__), "..", "word_lists")
ENABLE_URL = "https://raw.githubusercontent.com/dolph/dictionary/master/enable1.txt"
COMMON_URL = (
    "https://raw.githubusercontent.com/first20hours/google-10000-english/"
    "master/google-10000-english-no-swears.txt"
)

# Familiar 5-letter game words that may be missing from frequency lists.
CURATED_ANSWERS = frozenset({
    "apple", "beach", "brain", "bread", "crane", "dream", "flame", "ghost",
    "grape", "heart", "house", "light", "music", "night", "ocean", "plant",
    "queen", "river", "shade", "smile", "snake", "sound", "spare", "stone",
    "storm", "table", "tiger", "train", "water", "world", "write", "young",
})


def fetch(url: str) -> str:
    with urllib.request.urlopen(url, timeout=90) as response:
        return response.read().decode("utf-8")


def main() -> None:
    enable_words = {w.strip().lower() for w in fetch(ENABLE_URL).splitlines() if w.strip()}
    enable5 = {w for w in enable_words if len(w) == 5 and w.isalpha()}

    common_words = {w.strip().lower() for w in fetch(COMMON_URL).splitlines() if w.strip()}
    common5 = {w for w in common_words if len(w) == 5 and w.isalpha()}

    valid_guesses = sorted(enable5)
    answers = sorted((enable5 & common5) | (enable5 & CURATED_ANSWERS))

    os.makedirs(WORD_LISTS_DIR, exist_ok=True)
    guesses_path = os.path.join(WORD_LISTS_DIR, "valid_guesses.txt")
    answers_path = os.path.join(WORD_LISTS_DIR, "answers.txt")

    with open(guesses_path, "w", encoding="utf-8") as f:
        f.write("\n".join(valid_guesses) + "\n")
    with open(answers_path, "w", encoding="utf-8") as f:
        f.write("\n".join(answers) + "\n")

    print(f"Wrote {len(valid_guesses)} valid guesses and {len(answers)} answers.")


if __name__ == "__main__":
    main()
