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
    """Legacy helper — frontend keyboard no longer uses server re-score."""
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


def build_final_keyboard_state(rows: list[dict[str, str]]) -> dict[str, str]:
    """Mirror frontend buildFinalKeyboardState (chronological, gray bans yellow)."""
    final: dict[str, str] = {}
    yellow_banned: set[str] = set()
    priority = {"green": 3, "yellow": 2, "gray": 1}

    for row in rows:
        for letter, color in row.items():
            key = letter.lower()
            if color == "green":
                prev = final.get(key)
                if prev is None or priority[color] > priority[prev]:
                    final[key] = color
                continue
            if color == "gray":
                if final.get(key) == "yellow":
                    final.pop(key, None)
                yellow_banned.add(key)
                continue
            if color == "yellow" and key not in yellow_banned:
                prev = final.get(key)
                if prev is None or priority[color] > priority[prev]:
                    final[key] = color

    return final


def _row_letter_colors(secret: str, guess: str) -> dict[str, str]:
    state: dict[str, str] = {}
    feedback = score_guess(secret, guess)
    merge_keyboard_feedback(state, guess, feedback)
    return state


class TestChronologicalKeyboardState:
    def test_storm_then_sheep_clears_s_yellow(self):
        storm = {"s": "yellow", "t": "gray", "o": "gray", "r": "gray", "m": "gray"}
        sheep = {"s": "gray", "h": "gray", "e": "gray", "p": "gray"}
        assert "s" not in build_final_keyboard_state([storm, sheep])

    def test_yellow_does_not_return_after_gray_row(self):
        storm = {"s": "yellow", "t": "gray", "o": "gray", "r": "gray", "m": "gray"}
        sheep = {"s": "gray", "h": "gray", "e": "gray", "p": "gray"}
        assert "s" not in build_final_keyboard_state([storm, sheep, storm])

    def test_sauce_then_space_clears_stale_a_yellow(self):
        rows = [
            {"s": "green", "c": "green"},
            {"a": "yellow", "s": "gray", "e": "yellow"},
            {"a": "gray", "s": "gray", "p": "gray", "c": "gray", "e": "yellow"},
        ]
        final = build_final_keyboard_state(rows)
        assert "a" not in final
        assert final["s"] == "green"
        assert final["e"] == "yellow"

    def test_integration_learn_blend_sauce_space(self):
        game = create_test_game("learn", forced_mutations=["blend"])
        monkeypatch = pytest.MonkeyPatch()
        monkeypatch.setattr("game_logic.is_valid_guess", lambda w: True)
        try:
            process_guess(game, "sauce")
            result = process_guess(game, "space")
            assert result["keyboard_state"]["a"] == "gray"
        finally:
            monkeypatch.undo()

    def test_orange_not_downgraded_by_gray(self):
        rows = [
            {"p": "green", "a": "green"},
            {"p": "gray", "a": "green"},
        ]
        final = build_final_keyboard_state(rows)
        assert final["p"] == "green"
        assert final["a"] == "green"

    def test_first_row_yellow_persists_after_mutation(self):
        """Keyboard follows grid tiles; mutation alone must not clear yellow."""
        row = _row_letter_colors("plant", "penis")
        assert row.get("n") == "yellow"
        final = build_final_keyboard_state([row])
        assert final.get("n") == "yellow"
        assert final.get("p") == "green"


class TestStaleYellowAfterMutation:
    def test_realm_then_secret_becomes_cease(self):
        game = create_test_game("dream", forced_mutations=["cease"])
        monkeypatch = pytest.MonkeyPatch()
        monkeypatch.setattr("game_logic.is_valid_guess", lambda w: True)
        try:
            first = process_guess(game, "realm")
            assert first["keyboard_state"]["r"] == "gray"
            realm_row = _row_letter_colors("dream", "realm")
            assert build_final_keyboard_state([realm_row])["r"] == "yellow"

            second = process_guess(game, "reads")
            reads_row = _row_letter_colors("cease", "reads")
            final = build_final_keyboard_state([realm_row, reads_row])
            assert "r" not in final
            assert final.get("e") == "green"
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
        row = dict(grid_state)
        assert build_final_keyboard_state([row]) == {"a": "green", "b": "green"}


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
