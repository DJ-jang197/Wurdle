"""Flask application for Wurdle."""

import os

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

from game_logic import (
    MAX_ATTEMPTS,
    PRACTICE_GUESS_CHAIN,
    WORD_LENGTH,
    create_game,
    create_practice_game,
    get_game,
    process_guess,
)

app = Flask(__name__)
CORS(app)

FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


@app.route("/")
def index():
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.route("/<path:filename>")
def static_files(filename):
    return send_from_directory(FRONTEND_DIR, filename)


@app.route("/api/new-game", methods=["POST"])
def new_game():
    data = request.get_json(silent=True) or {}
    if data.get("practice"):
        game = create_practice_game()
        return jsonify(
            {
                "game_id": game.game_id,
                "word_length": WORD_LENGTH,
                "max_attempts": MAX_ATTEMPTS,
                "practice_mode": True,
                "practice_chain": PRACTICE_GUESS_CHAIN,
            }
        )

    game = create_game()
    return jsonify(
        {
            "game_id": game.game_id,
            "word_length": WORD_LENGTH,
            "max_attempts": MAX_ATTEMPTS,
            "practice_mode": False,
        }
    )


@app.route("/api/guess", methods=["POST"])
def guess():
    data = request.get_json(silent=True) or {}
    game_id = data.get("game_id")
    raw_guess = data.get("guess", "")

    if not game_id:
        return jsonify({"status": "error", "error": "Missing game_id"}), 400

    game = get_game(game_id)
    if game is None:
        return jsonify({"status": "error", "error": "Game not found"}), 404

    result = process_guess(game, raw_guess)

    if result.get("status") == "invalid_word":
        return jsonify(result), 400

    return jsonify(result)


if __name__ == "__main__":
    app.run(debug=True, port=5000)
