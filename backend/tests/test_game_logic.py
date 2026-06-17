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
        secret = "aaaaa"
        locked = [False] * WORD_LENGTH
        for _ in range(100):
            new_secret, idx = mutate(secret, locked)
            assert new_secret[idx] != secret[idx]

    def test_no_unlocked_raises(self):
        with pytest.raises(ValueError):
            mutate("crane", [True] * WORD_LENGTH)


class TestGameState:
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
