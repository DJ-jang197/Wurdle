"""Tests for API security helpers and hardening."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app import app
from game_logic import (
    clear_games,
    create_game,
    get_game,
    prune_stale_games,
)
from security import (
    GUESS_LIMITER,
    NEW_GAME_LIMITER,
    clear_rate_limiters,
    is_safe_static_path,
    parse_game_id,
    parse_guess,
    parse_word_list,
)


@pytest.fixture
def client():
    clear_games()
    clear_rate_limiters()
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client
    clear_games()
    clear_rate_limiters()


def test_parse_game_id_accepts_uuid():
    value = "550e8400-e29b-41d4-a716-446655440000"
    assert parse_game_id(value) == value


def test_parse_game_id_rejects_garbage():
    assert parse_game_id("not-a-uuid") is None
    assert parse_game_id("") is None
    assert parse_game_id(None) is None


def test_parse_guess_requires_five_letters():
    assert parse_guess("crane") == "crane"
    assert parse_guess("CRANE") == "crane"
    assert parse_guess("cr") is None
    assert parse_guess("crane!") is None
    assert parse_guess("12345") is None


def test_parse_word_list():
    assert parse_word_list(["dream", "cease"]) == ["dream", "cease"]
    assert parse_word_list(None) == []
    assert parse_word_list("nope") is None
    assert parse_word_list(["ok", "bad"]) is None


def test_is_safe_static_path():
    assert is_safe_static_path("style.css")
    assert is_safe_static_path("script.js")
    assert not is_safe_static_path("../secret.txt")
    assert not is_safe_static_path("style.css/extra")
    assert not is_safe_static_path("")


def test_guess_rejects_invalid_game_id(client):
    resp = client.post("/api/guess", json={"game_id": "nope", "guess": "crane"})
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "Invalid game_id"


def test_guess_rejects_malformed_word(client):
    new_resp = client.post("/api/new-game", json={})
    game_id = new_resp.get_json()["game_id"]

    resp = client.post("/api/guess", json={"game_id": game_id, "guess": "no"})
    assert resp.status_code == 400
    assert "5 letters" in resp.get_json()["error"]


def test_static_path_traversal_blocked(client):
    resp = client.get("/../app.py")
    assert resp.status_code == 404


def test_test_endpoint_hidden_by_default():
    clear_games()
    app.config["TESTING"] = False
    with app.test_client() as client:
        resp = client.post("/api/test/new-game", json={"secret": "crane"})
        assert resp.status_code == 404
    app.config["TESTING"] = True


def test_rate_limit_new_game(monkeypatch):
    clear_rate_limiters()
    app.config["TESTING"] = False
    monkeypatch.setattr(NEW_GAME_LIMITER, "max_requests", 2)

    with app.test_client() as client:
        assert client.post("/api/new-game", json={}).status_code == 200
        assert client.post("/api/new-game", json={}).status_code == 200
        blocked = client.post("/api/new-game", json={})
        assert blocked.status_code == 429

    app.config["TESTING"] = True
    clear_rate_limiters()


def test_prune_stale_games(monkeypatch):
    clear_games()
    game = create_game()
    stale = get_game(game.game_id)
    assert stale is not None
    stale.updated_at = datetime.now(timezone.utc) - timedelta(hours=48)
    stale.status = "in_progress"
    assert prune_stale_games() == 1
    assert get_game(game.game_id) is None


def test_max_games_returns_503(client, monkeypatch):
    clear_games()
    monkeypatch.setattr("game_logic.MAX_GAMES", 1)
    assert client.post("/api/new-game", json={}).status_code == 200
    busy = client.post("/api/new-game", json={})
    assert busy.status_code == 503
