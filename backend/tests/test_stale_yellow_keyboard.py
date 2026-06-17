"""Tests for keyboard yellow clearing when the secret mutates a letter out."""

from __future__ import annotations

import pytest

from app import app  # noqa: E402
from game_logic import (
    WORD_LENGTH,
    clear_games,
    compute_keyboard_state,
    create_test_game,
    merge_keyboard_feedback,
    process_guess,
    score_guess,
)


@pytest.fixture(autouse=True)
def _clear_games():
    clear_games()
    yield
    clear_games()


@pytest.fixture
def client():
    clear_games()
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client
    clear_games()


def reconcile_stale_yellow(grid_state: dict[str, str], server_state: dict[str, str]) -> dict[str, str]:
    """Mirror frontend reconcileStaleYellowWithServer."""
    final = dict(grid_state)
    for letter, color in grid_state.items():
        if color == "yellow":
            server_color = server_state.get(letter)
            if server_color not in ("yellow", "green"):
                final.pop(letter, None)
    return final


def _grid_keyboard_from_guesses(secret: str, guesses: list[str]) -> dict[str, str]:
    state: dict[str, str] = {}
    for guess in guesses:
        feedback = score_guess(secret, guess)
        merge_keyboard_feedback(state, guess, feedback)
    return {letter: color for letter, color in state.items() if color != "gray"}


class TestReconcileStaleYellow:
    def test_drops_yellow_when_server_says_gray(self):
        grid = {"r": "yellow", "e": "yellow", "m": "green"}
        server = {"r": "gray", "e": "green", "m": "green", "c": "green"}
        assert reconcile_stale_yellow(grid, server) == {"e": "yellow", "m": "green"}

    def test_keeps_yellow_when_still_in_secret(self):
        grid = {"r": "yellow", "e": "yellow"}
        server = {"r": "yellow", "e": "yellow"}
        assert reconcile_stale_yellow(grid, server) == {"r": "yellow", "e": "yellow"}

    def test_keeps_orange_when_server_green(self):
        grid = {"r": "green", "e": "yellow"}
        server = {"r": "green", "e": "gray"}
        assert reconcile_stale_yellow(grid, server) == {"r": "green"}

    def test_does_not_add_colors_from_server(self):
        grid = {"e": "yellow"}
        server = {"r": "gray", "e": "yellow", "a": "yellow"}
        assert reconcile_stale_yellow(grid, server) == {"e": "yellow"}


class TestStaleYellowAfterMutation:
    def test_realm_then_secret_becomes_cease(self):
        game = create_test_game("dream", forced_mutations=["cease"])
        monkeypatch = pytest.MonkeyPatch()
        monkeypatch.setattr("game_logic.is_valid_guess", lambda w: True)
        try:
            first = process_guess(game, "realm")
            assert first["keyboard_state"]["r"] == "gray"
            grid_state = _grid_keyboard_from_guesses("dream", ["realm"])
            assert grid_state["r"] == "yellow"
            assert reconcile_stale_yellow(grid_state, first["keyboard_state"]) == {
                "e": "yellow",
                "a": "yellow",
                "m": "green",
            }

            second = process_guess(game, "reads")
            assert second["keyboard_state"]["r"] == "gray"
            grid_state = _grid_keyboard_from_guesses("dream", ["realm", "reads"])
            assert grid_state["r"] == "yellow"
            assert reconcile_stale_yellow(grid_state, second["keyboard_state"]) == {
                "e": "yellow",
                "a": "yellow",
                "m": "green",
            }
        finally:
            monkeypatch.undo()

    def test_yellow_persists_when_letter_still_in_secret(self):
        guesses = ["realm"]
        before = compute_keyboard_state("dream", guesses, [False] * WORD_LENGTH)
        after = compute_keyboard_state("dread", guesses, [False] * WORD_LENGTH)
        assert before["r"] == "yellow"
        assert after["r"] == "yellow"

    def test_forced_mutation_sets_mutated_position(self):
        game = create_test_game("dream", forced_mutations=["cease"])
        monkeypatch = pytest.MonkeyPatch()
        monkeypatch.setattr("game_logic.is_valid_guess", lambda w: True)
        try:
            result = process_guess(game, "realm")
            assert game.secret == "cease"
            assert result["mutated_position"] is not None
            assert result["mutated_from"] != result["mutated_to"]
        finally:
            monkeypatch.undo()

    def test_duplicate_letter_yellow_only_clears_when_fully_out(self):
        feedback = score_guess("aabbb", "abbba")
        grid_state: dict[str, str] = {}
        merge_keyboard_feedback(grid_state, "abbba", feedback)
        server = compute_keyboard_state("abcqz", ["abbba"], [False] * 5)
        assert grid_state["b"] == "green"
        assert server["b"] == "green"
        assert reconcile_stale_yellow(grid_state, server) == {"a": "green", "b": "green"}


class TestStaleYellowApi:
    def test_test_new_game_endpoint(self, client, monkeypatch):
        monkeypatch.setattr("game_logic.is_valid_guess", lambda w: True)
        resp = client.post(
            "/api/test/new-game",
            json={"secret": "dream", "forced_mutations": ["cease"]},
        )
        assert resp.status_code == 200
        game_id = resp.get_json()["game_id"]

        guess = client.post(
            "/api/guess",
            json={"game_id": game_id, "guess": "realm"},
        )
        assert guess.status_code == 200
        data = guess.get_json()
        assert data["keyboard_state"]["r"] == "gray"

    def test_test_new_game_hidden_outside_testing(self):
        from app import app

        app.config["TESTING"] = False
        with app.test_client() as client:
            resp = client.post("/api/test/new-game", json={"secret": "dream"})
            assert resp.status_code == 404
        app.config["TESTING"] = True
