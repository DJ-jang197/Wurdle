"""
Build an 8-word practice chain: each step changes exactly one letter and every
word is in valid_guesses.txt (ENABLE / Webster-style list). Prefer words from
answers.txt (common secrets) when multiple chains exist.
"""

from __future__ import annotations

import string
from collections import deque
from functools import lru_cache

from word_loader import get_answers, get_valid_guesses

CHAIN_LENGTH = 8
WORD_LENGTH = 5

# Resolved offline by scripts/find_practice_chain.py — all one-letter steps, all valid.
PRACTICE_ANSWER = "bound"
PRACTICE_GUESS_CHAIN = [
    "could",
    "would",
    "wound",
    "sound",
    "round",
    "pound",
    "found",
    "bound",
]

# Try these answer-list secrets first (common words, fast BFS).
_PREFERRED_ENDS = (
    "bound",
    "found",
    "sound",
    "world",
    "round",
    "pound",
    "would",
    "wound",
    "write",
    "white",
    "whole",
    "those",
    "chase",
    "ready",
    "horse",
    "bread",
    "stone",
    "light",
    "house",
    "water",
    "ghost",
)


def one_letter_diff(a: str, b: str) -> bool:
    """True if two equal-length words differ in exactly one position."""
    return len(a) == len(b) and sum(x != y for x, y in zip(a, b)) == 1


def neighbors(word: str, word_set: frozenset[str]) -> list[str]:
    """All one-letter variants of `word` that exist in `word_set`."""
    result: list[str] = []
    for i in range(WORD_LENGTH):
        prefix, suffix = word[:i], word[i + 1 :]
        for letter in string.ascii_lowercase:
            if letter == word[i]:
                continue
            candidate = prefix + letter + suffix
            if candidate in word_set:
                result.append(candidate)
    return result


def mutation_options(
    secret: str,
    locked: list[bool],
    word_set: frozenset[str],
) -> list[tuple[str, int]]:
    """
    Valid one-letter moves from `secret` at unlocked positions.
    Returns (new_secret, mutated_index) pairs; every new_secret is in word_set.
    """
    options: list[tuple[str, int]] = []
    for i in range(WORD_LENGTH):
        if locked[i]:
            continue
        prefix, suffix = secret[:i], secret[i + 1 :]
        for letter in string.ascii_lowercase:
            if letter == secret[i]:
                continue
            candidate = prefix + letter + suffix
            if candidate in word_set:
                options.append((candidate, i))
    return options


def find_chains_bfs(
    end: str,
    word_set: frozenset[str],
    length: int = CHAIN_LENGTH,
    max_results: int = 50,
) -> list[list[str]]:
    """Return chains [start, ..., end] where each consecutive pair differs by one letter."""
    if end not in word_set:
        return []

    queue: deque[tuple[str, list[str]]] = deque([(end, [end])])
    found: list[list[str]] = []
    seen_depth: dict[str, int] = {end: 1}

    while queue and len(found) < max_results:
        head, path = queue.popleft()
        if len(path) == length:
            found.append(list(reversed(path)))
            continue
        if len(path) > length:
            continue

        for nxt in neighbors(head, word_set):
            if nxt in path:
                continue
            new_path = path + [nxt]
            depth = len(new_path)
            if seen_depth.get(nxt, 0) >= depth:
                continue
            seen_depth[nxt] = depth
            queue.append((nxt, new_path))

    return found


def _score_chain(chain: list[str], answers: frozenset[str]) -> tuple[int, int, str]:
    """Rank chains: prefer all-answer words, then more answer words, then lexicographic start."""
    answer_count = sum(1 for w in chain if w in answers)
    all_answers = answer_count == len(chain)
    return (1 if all_answers else 0, answer_count, chain[0])


def find_best_practice_chain(
    *,
    end: str | None = None,
    word_set: frozenset[str] | None = None,
    answers: frozenset[str] | None = None,
    prefer_answers_only: bool = True,
) -> list[str] | None:
    """
    Find an 8-word chain ending at `end` (or a preferred common answer).
    Searches the answer list first for familiar words, then full valid guesses.
    """
    guesses = word_set if word_set is not None else get_valid_guesses()
    answer_set = answers if answers is not None else get_answers()

    search_sets: list[frozenset[str]] = (
        [answer_set] if prefer_answers_only else [answer_set, guesses]
    )
    targets: list[str] = [end.lower()] if end else list(_PREFERRED_ENDS)

    candidates: list[list[str]] = []
    for vocab in search_sets:
        for target in targets:
            if target not in vocab:
                continue
            candidates.extend(
                find_chains_bfs(target, vocab, CHAIN_LENGTH, max_results=15)
            )
        if candidates:
            break

    if not candidates:
        return None

    candidates.sort(key=lambda c: _score_chain(c, answer_set), reverse=True)
    best = candidates[0]
    validate_practice_chain(best, guesses, answer_set)
    return best


def validate_practice_chain(
    chain: list[str],
    word_set: frozenset[str] | None = None,
    answers: frozenset[str] | None = None,
) -> None:
    """Raise ValueError if chain is not a valid one-letter practice sequence."""
    guesses = word_set if word_set is not None else get_valid_guesses()
    if len(chain) != CHAIN_LENGTH:
        raise ValueError(f"Chain must have {CHAIN_LENGTH} words, got {len(chain)}")
    for word in chain:
        if word not in guesses:
            raise ValueError(f"Not a valid dictionary word: {word!r}")
    for i in range(len(chain) - 1):
        if not one_letter_diff(chain[i], chain[i + 1]):
            raise ValueError(
                f"Step {i + 1} is not one letter apart: {chain[i]!r} -> {chain[i + 1]!r}"
            )


@lru_cache(maxsize=1)
def get_mutable_answers() -> frozenset[str]:
    """Answer words with at least one valid one-letter neighbor in the full dictionary."""
    guesses = get_valid_guesses()
    answers = get_answers()
    return frozenset(
        word
        for word in answers
        if mutation_options(word, [False] * WORD_LENGTH, guesses)
    )


@lru_cache(maxsize=1)
def get_practice_chain() -> tuple[str, tuple[str, ...]]:
    """Return (secret, guess_chain) validated against current word lists."""
    chain = list(PRACTICE_GUESS_CHAIN)
    validate_practice_chain(chain)
    return chain[-1], tuple(chain)
