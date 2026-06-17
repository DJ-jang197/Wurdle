"""
Prepare and validate the built-in 8-word practice chain.

Uses the ENABLE / Webster-style lists in word_lists/ (no extra library needed).
Each consecutive word differs by exactly one letter; all words are valid guesses.

Usage (from backend/):
    python scripts/prepare_practice_chain.py
    python scripts/prepare_practice_chain.py --end bound --write
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from practice_chain import (  # noqa: E402
    CHAIN_LENGTH,
    PRACTICE_ANSWER,
    PRACTICE_GUESS_CHAIN,
    find_best_practice_chain,
    one_letter_diff,
    validate_practice_chain,
)
from word_loader import get_answers, get_valid_guesses  # noqa: E402

PRACTICE_CHAIN_PATH = BACKEND_DIR / "practice_chain.py"


def write_chain_to_module(chain: list[str]) -> None:
    """Persist PRACTICE_ANSWER and PRACTICE_GUESS_CHAIN into practice_chain.py."""
    text = PRACTICE_CHAIN_PATH.read_text(encoding="utf-8")
    answer = chain[-1]
    block = "PRACTICE_GUESS_CHAIN = [\n" + "".join(
        f'    "{word}",\n' for word in chain
    ) + "]"
    text = re.sub(
        r'PRACTICE_ANSWER = "[^"]*"',
        f'PRACTICE_ANSWER = "{answer}"',
        text,
    )
    text = re.sub(
        r"PRACTICE_GUESS_CHAIN = \[[\s\S]*?\]",
        block,
        text,
        count=1,
    )
    PRACTICE_CHAIN_PATH.write_text(text, encoding="utf-8")


def main() -> None:
    """CLI: validate or regenerate the built-in practice chain."""
    parser = argparse.ArgumentParser(
        description="Prepare a valid 8-word one-letter practice chain."
    )
    parser.add_argument("--end", help="Last word (winning guess / secret)")
    parser.add_argument(
        "--write",
        action="store_true",
        help="Write the chosen chain into practice_chain.py",
    )
    args = parser.parse_args()

    guesses = get_valid_guesses()
    answers = get_answers()

    print(f"Dictionary: {len(guesses)} valid guesses, {len(answers)} answer words")

    chain = find_best_practice_chain(
        end=args.end.lower() if args.end else None,
        word_set=guesses,
        answers=answers,
        prefer_answers_only=True,
    )
    if not chain:
        print("No chain found. Try --end with another answer word.", file=sys.stderr)
        sys.exit(1)

    validate_practice_chain(chain, guesses, answers)

    print(f"\nValid {CHAIN_LENGTH}-word chain (secret = {chain[-1]!r}):")
    for i, word in enumerate(chain, 1):
        step = ""
        if i > 1:
            prev = chain[i - 2]
            pos = next(j for j in range(5) if prev[j] != word[j])
            step = f"  ({prev[pos]} -> {word[pos]} at pos {pos + 1})"
        print(f"  {i}. {word}{step}")
        if i > 1:
            assert one_letter_diff(chain[i - 2], word)

    if args.write:
        write_chain_to_module(chain)
        print(f"\nWrote chain to {PRACTICE_CHAIN_PATH}")
    else:
        print("\nBuilt-in chain currently in practice_chain.py:")
        validate_practice_chain(list(PRACTICE_GUESS_CHAIN), guesses, answers)
        print(f"  secret = {PRACTICE_ANSWER!r}")
        print(f"  chain  = {PRACTICE_GUESS_CHAIN}")


if __name__ == "__main__":
    main()
