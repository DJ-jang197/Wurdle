"""Tests for word list loading and validation."""

import pytest

from word_loader import (
    get_answers,
    get_valid_guesses,
    is_valid_guess,
    pick_random_answer,
    reload_word_lists,
    without_plural_s_endings,
)


@pytest.fixture(autouse=True)
def _fresh_word_lists():
    reload_word_lists()
    yield
    reload_word_lists()


def test_word_lists_load():
    answers = get_answers()
    guesses = get_valid_guesses()
    assert len(answers) > 0
    assert len(guesses) > len(answers)
    assert all(len(w) == 5 for w in answers)
    assert all(len(w) == 5 for w in guesses)
    assert all(w.isalpha() for w in guesses)
    assert answers <= guesses


def test_answers_are_common_english_samples():
    answers = get_answers()
    for word in ("crane", "apple", "house", "water", "light"):
        assert word in answers


def test_proper_nouns_and_regions_excluded():
    guesses = get_valid_guesses()
    for excluded in ("china", "texas", "japan", "paris", "spain", "james"):
        assert excluded not in guesses


def test_is_valid_guess_known_good():
    assert is_valid_guess("crane") is True
    assert is_valid_guess("CRANE") is True
    assert is_valid_guess("apple") is True


def test_is_valid_guess_known_bad():
    assert is_valid_guess("zzzzz") is False
    assert is_valid_guess("abcd") is False
    assert is_valid_guess("abcdef") is False
    assert is_valid_guess("CRAN") is False


def test_without_plural_s_endings_prefers_non_s():
    answers = get_answers()
    preferred = without_plural_s_endings(answers)
    assert preferred
    assert all(not word.endswith("s") for word in preferred)
    assert len(preferred) < len(answers)


def test_pick_random_answer_avoids_s_when_possible(monkeypatch):
    picks: list[str] = []

    def fake_choice(pool):
        picks.append(pool[0])
        return pool[0]

    monkeypatch.setattr("random.choice", fake_choice)
    pick_random_answer()
    assert not picks[0].endswith("s")
