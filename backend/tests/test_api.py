"""Integration tests for Flask API."""

import pytest

from app import app
from game_logic import clear_games, get_game


@pytest.fixture
def client():
    clear_games()
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client
    clear_games()


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.get_json() == {"status": "ok"}


def test_new_game_returns_id_not_secret(client):
    resp = client.post("/api/new-game", json={})
    assert resp.status_code == 200
    data = resp.get_json()
    assert "game_id" in data
    assert "secret" not in data
    assert "secret_word" not in data
    assert data["word_length"] == 5
    assert data["max_attempts"] == 8


def test_invalid_word_does_not_consume_attempt(client, monkeypatch):
    monkeypatch.setattr("game_logic.is_valid_guess", lambda w: w == "valid")

    new_resp = client.post("/api/new-game", json={})
    game_id = new_resp.get_json()["game_id"]

    bad = client.post(
        "/api/guess", json={"game_id": game_id, "guess": "zzzzz"}
    )
    assert bad.status_code == 400
    assert bad.get_json()["status"] == "invalid_word"

    game = get_game(game_id)
    assert game.attempts_used == 0

    good = client.post(
        "/api/guess", json={"game_id": game_id, "guess": "valid"}
    )
    assert good.status_code == 200
    assert good.get_json()["attempts_used"] == 1


def test_independent_games(client, monkeypatch):
    monkeypatch.setattr("game_logic.is_valid_guess", lambda w: True)

    g1 = client.post("/api/new-game", json={}).get_json()["game_id"]
    g2 = client.post("/api/new-game", json={}).get_json()["game_id"]

    client.post("/api/guess", json={"game_id": g1, "guess": "aaaaa"})
    client.post("/api/guess", json={"game_id": g1, "guess": "bbbbb"})

    resp = client.post("/api/guess", json={"game_id": g2, "guess": "ccccc"})
    assert resp.get_json()["attempts_used"] == 1


def test_win_reveals_secret(client, monkeypatch):
    new_resp = client.post("/api/new-game", json={})
    game_id = new_resp.get_json()["game_id"]
    game = get_game(game_id)
    secret = game.secret

    monkeypatch.setattr(
        "game_logic.is_valid_guess", lambda w: w == secret
    )

    resp = client.post(
        "/api/guess", json={"game_id": game_id, "guess": secret}
    )
    data = resp.get_json()
    assert data["status"] == "won"
    assert data["secret_word"] == secret


def test_loss_reveals_secret(client, monkeypatch):
    new_resp = client.post("/api/new-game", json={})
    game_id = new_resp.get_json()["game_id"]

    monkeypatch.setattr("game_logic.is_valid_guess", lambda w: True)

    for _ in range(8):
        resp = client.post(
            "/api/guess", json={"game_id": game_id, "guess": "xxxxx"}
        )

    data = resp.get_json()
    assert data["status"] == "lost"
    assert "secret_word" in data


def test_in_progress_no_secret(client, monkeypatch):
    new_resp = client.post("/api/new-game", json={})
    game_id = new_resp.get_json()["game_id"]
    monkeypatch.setattr("game_logic.is_valid_guess", lambda w: True)

    resp = client.post(
        "/api/guess", json={"game_id": game_id, "guess": "aaaaa"}
    )
    data = resp.get_json()
    assert data["status"] == "in_progress"
    assert "secret_word" not in data
    assert "secret_timeline" not in data
    assert "keyboard_state" in data


def test_win_includes_secret_timeline(client, monkeypatch):
    new_resp = client.post("/api/new-game", json={})
    game_id = new_resp.get_json()["game_id"]
    game = get_game(game_id)
    secret = game.secret

    monkeypatch.setattr("game_logic.is_valid_guess", lambda w: w == secret)

    resp = client.post(
        "/api/guess", json={"game_id": game_id, "guess": secret}
    )
    data = resp.get_json()
    assert data["status"] == "won"
    assert "secret_timeline" in data
    assert data["secret_timeline"][0]["secret"] == secret
