"""Tests for practice word chain generation and validation."""

from practice_chain import (
    PRACTICE_ANSWER,
    PRACTICE_GUESS_CHAIN,
    find_best_practice_chain,
    one_letter_diff,
    validate_practice_chain,
)
from word_loader import get_answers, get_valid_guesses


def test_builtin_chain_is_valid():
    guesses = get_valid_guesses()
    answers = get_answers()
    validate_practice_chain(PRACTICE_GUESS_CHAIN, guesses, answers)
    assert PRACTICE_GUESS_CHAIN[-1] == PRACTICE_ANSWER


def test_builtin_chain_one_letter_steps():
    for i in range(len(PRACTICE_GUESS_CHAIN) - 1):
        assert one_letter_diff(PRACTICE_GUESS_CHAIN[i], PRACTICE_GUESS_CHAIN[i + 1])


def test_find_chain_for_bound():
    chain = find_best_practice_chain(end="bound")
    assert chain is not None
    assert len(chain) == 8
    assert chain[-1] == "bound"
    validate_practice_chain(chain)


def test_find_chain_prefers_answer_words():
    chain = find_best_practice_chain(end="bound")
    assert chain is not None
    answers = get_answers()
    assert all(word in answers for word in chain)
