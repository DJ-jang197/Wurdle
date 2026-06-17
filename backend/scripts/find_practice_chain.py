"""
Find an 8-word practice chain: each step changes exactly one letter;
every word must be in valid_guesses.txt (ENABLE / Webster-style list).

Usage (from backend/):
    python scripts/find_practice_chain.py
    python scripts/find_practice_chain.py --end bound
    python scripts/find_practice_chain.py --full-guesses
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from practice_chain import (  # noqa: E402
    find_best_practice_chain,
    one_letter_diff,
    validate_practice_chain,
)
from word_loader import get_answers, get_valid_guesses  # noqa: E402


def main() -> None:
    """CLI: search for and print a valid eight-word practice chain."""
    parser = argparse.ArgumentParser(description="Find a one-letter-diff word chain.")
    parser.add_argument("--end", help="Force last word (secret) in chain")
    parser.add_argument(
        "--full-guesses",
        action="store_true",
        help="Allow obscure words outside answers.txt",
    )
    args = parser.parse_args()

    answers = get_answers()
    guesses = get_valid_guesses()

    chain = find_best_practice_chain(
        end=args.end.lower() if args.end else None,
        word_set=guesses,
        answers=answers,
        prefer_answers_only=not args.full_guesses,
    )

    if not chain:
        print("No chain found.", file=sys.stderr)
        sys.exit(1)

    validate_practice_chain(chain, guesses, answers)

    print(f"Chain ({len(chain)} words), secret = {chain[-1]!r}:")
    for i, word in enumerate(chain, 1):
        mark = " *" if word in answers else ""
        print(f"  {i}. {word}{mark}")
        if i < len(chain):
            assert one_letter_diff(chain[i - 1], chain[i])

    print("\nPython literal:")
    print("PRACTICE_ANSWER =", repr(chain[-1]))
    print("PRACTICE_GUESS_CHAIN = [")
    for word in chain:
        print(f'    "{word}",')
    print("]")


if __name__ == "__main__":
    main()
