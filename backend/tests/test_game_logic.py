"""Unit tests for pure game logic."""

import random

import pytest

from game_logic import (
    MAX_ATTEMPTS,
    WORD_LENGTH,
    GameState,
    build_known_state,
    clear_games,
    compute_keyboard_state,
    merge_keyboard_feedback,
    mutate,
    score_guess,
)


@pytest.fixture(autouse=True)
def _clear_games():
    clear_games()
    yield
    clear_games()


class TestScoreGuess:
    def test_duplicate_letters_green_yellow_gray(self):
        # secret "aabbb", guess "abbba" — one b in guess, multiple b's in secret
        result = score_guess("aabbb", "abbba")
        assert result == ["green", "yellow", "green", "green", "yellow"]

    def test_all_green(self):
        assert score_guess("crane", "crane") == ["green"] * WORD_LENGTH

    def test_all_gray(self):
        assert score_guess("crane", "xyzzz") == ["gray"] * WORD_LENGTH

    def test_apple_secret_one_p_in_guess(self):
        # APPLE has one P; only one P in PUPPY can be colored (green at pos 2).
        assert score_guess("apple", "puppy") == [
            "yellow",
            "gray",
            "green",
            "gray",
            "gray",
        ]

    def test_apple_secret_papal(self):
        assert score_guess("apple", "papal") == [
            "yellow",
            "yellow",
            "green",
            "gray",
            "yellow",
        ]

    def test_dread_secret_duplicate_d_in_guess(self):
        # DREAD has D at positions 0 and 4; two D's in guess can both be green.
        assert score_guess("dread", "ddddd") == [
            "green",
            "gray",
            "gray",
            "gray",
            "green",
        ]

    def test_eerie_allen_duplicate_e(self):
        # Secret has three E's; guess has two — only two yellows, not three.
        assert score_guess("eerie", "allen") == [
            "gray",
            "gray",
            "gray",
            "yellow",
            "gray",
        ]

    def test_case_insensitive_scoring(self):
        assert score_guess("APPLE", "ApPlE") == ["green"] * WORD_LENGTH


class TestKeyboardMergeDuplicates:
    def test_row_merge_picks_best_color_for_duplicate_letter(self):
        feedback = score_guess("apple", "puppy")
        state: dict[str, str] = {}
        merge_keyboard_feedback(state, "puppy", feedback)
        assert state["p"] == "green"
        assert state["u"] == "gray"
        assert state["y"] == "gray"

    def test_keyboard_state_dread_ddddd(self):
        state = compute_keyboard_state("dread", ["ddddd"], [False] * WORD_LENGTH)
        assert state["d"] == "green"

    def test_keyboard_state_apple_papal(self):
        state = compute_keyboard_state("apple", ["papal"], [False] * WORD_LENGTH)
        assert state["p"] == "green"
        assert state["a"] == "yellow"
        assert state["l"] == "yellow"


class TestMutate:
    def test_locked_positions_never_mutate(self):
        secret = "crane"
        locked = [True, False, True, False, True]
        for _ in range(100):
            new_secret, idx = mutate(secret, locked)
            assert idx in (1, 3)
            assert new_secret[0] == secret[0]
            assert new_secret[2] == secret[2]
            assert new_secret[4] == secret[4]

    def test_mutation_always_changes_letter(self):
        secret = "crane"
        locked = [False] * WORD_LENGTH
        for _ in range(50):
            new_secret, idx = mutate(secret, locked)
            assert new_secret[idx] != secret[idx]

    def test_mutation_stays_in_dictionary(self):
        from word_loader import get_answers, get_valid_guesses

        answers = get_answers()
        guesses = get_valid_guesses()
        secret = "crane"
        locked = [False] * WORD_LENGTH
        for _ in range(50):
            new_secret, _ = mutate(secret, locked)
            assert new_secret in answers or new_secret in guesses

    def test_mutation_changes_exactly_one_letter(self):
        secret = "crane"
        locked = [False] * WORD_LENGTH
        for _ in range(100):
            new_secret, _ = mutate(secret, locked)
            diff_count = sum(a != b for a, b in zip(secret, new_secret))
            assert diff_count == 1

    def test_no_unlocked_raises(self):
        with pytest.raises(ValueError):
            mutate("crane", [True] * WORD_LENGTH)


class TestGameState:
    def test_create_has_initial_timeline(self):
        game = GameState(game_id="t", secret="crane")
        game.secret_timeline.append({"after_attempt": 0, "secret": "crane"})
        assert game.secret_timeline[0]["secret"] == "crane"

    def test_win_no_mutation(self, monkeypatch):
        game = GameState(game_id="test", secret="crane")
        monkeypatch.setattr(
            "game_logic.is_valid_guess", lambda w: w == "crane"
        )
        result = game.apply_guess("crane")
        assert result["status"] == "won"
        assert "mutated_position" not in result
        assert result["secret_word"] == "crane"

    def test_loss_on_eighth_guess(self, monkeypatch):
        game = GameState(game_id="test", secret="crane")
        monkeypatch.setattr("game_logic.is_valid_guess", lambda w: True)

        for i in range(MAX_ATTEMPTS - 1):
            result = game.apply_guess("xxxxx")
            assert result["status"] == "in_progress"

        result = game.apply_guess("xxxxx")
        assert result["status"] == "lost"
        assert "secret_word" in result

    def test_invalid_word_does_not_consume_attempt(self, monkeypatch):
        game = GameState(game_id="test", secret="crane")
        monkeypatch.setattr("game_logic.is_valid_guess", lambda w: False)
        result = game.apply_guess("crane")
        assert result["status"] == "invalid_word"
        assert game.attempts_used == 0

    def test_locking_on_green(self, monkeypatch):
        game = GameState(game_id="test", secret="crane")
        monkeypatch.setattr("game_logic.is_valid_guess", lambda w: True)
        result = game.apply_guess("cxxxx")
        assert result["locked_positions"][0] is True
        assert result["known_state"][0] == "c"

    def test_one_secret_letter_mutates_per_wrong_guess(self, monkeypatch):
        game = GameState(game_id="test", secret="crane")
        monkeypatch.setattr("game_logic.is_valid_guess", lambda w: True)
        previous_secret = game.secret
        result = game.apply_guess("xxxxx")
        assert result["status"] == "in_progress"
        diff_count = sum(
            a != b for a, b in zip(previous_secret, game.secret)
        )
        assert diff_count == 1
        assert result["mutated_position"] is not None

    def test_secret_timeline_always_valid_words(self, monkeypatch):
        from word_loader import get_answers, get_valid_guesses

        answers = get_answers()
        guesses = get_valid_guesses()
        game = GameState(game_id="test", secret="crane")
        monkeypatch.setattr("game_logic.is_valid_guess", lambda w: True)

        for _ in range(MAX_ATTEMPTS - 1):
            game.apply_guess("xxxxx")

        for entry in game.secret_timeline:
            word = entry["secret"]
            assert word in answers or word in guesses, f"Invalid secret in timeline: {word!r}"


class TestBuildKnownState:
    def test_shows_locked_only(self):
        assert build_known_state("crane", [True, False, True, False, False]) == [
            "c",
            "_",
            "a",
            "_",
            "_",
        ]


class TestKeyboardState:
    def test_locked_letters_are_green(self):
        state = compute_keyboard_state("crane", [], [True, False, False, False, False])
        assert state["c"] == "green"

    def test_recomputed_after_secret_changes(self):
        guesses = ["amzxy"]
        before = compute_keyboard_state("abcmz", guesses, [False] * WORD_LENGTH)
        after = compute_keyboard_state("abcqz", guesses, [False] * WORD_LENGTH)
        assert before.get("m") == "yellow"
        assert after.get("m") == "gray"

    def test_guess_response_includes_keyboard_state(self, monkeypatch):
        game = GameState(game_id="test", secret="crane")
        monkeypatch.setattr("game_logic.is_valid_guess", lambda w: True)
        result = game.apply_guess("track")
        assert "keyboard_state" in result
        assert isinstance(result["keyboard_state"], dict)
