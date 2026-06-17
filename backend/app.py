"""Flask application for Wurdle."""

from __future__ import annotations

import logging
import os
import sys

from flask import Flask, abort, jsonify, request, send_from_directory
from flask_cors import CORS
from werkzeug.exceptions import HTTPException

from game_logic import (
    MAX_ATTEMPTS,
    PRACTICE_GUESS_CHAIN,
    WORD_LENGTH,
    GameStoreFullError,
    create_game,
    create_practice_game,
    create_test_game,
    get_game,
    process_guess,
)
from security import (
    GUESS_LIMITER,
    NEW_GAME_LIMITER,
    is_safe_static_path,
    parse_game_id,
    parse_guess,
    parse_word_list,
    rate_limit,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config["TESTING"] = os.getenv("WURDLE_TESTING", "").lower() in ("1", "true")

_cors_origins = os.getenv("WURDLE_CORS_ORIGINS", "").strip()
if _cors_origins:
    CORS(app, origins=[o.strip() for o in _cors_origins.split(",") if o.strip()])
else:
    CORS(app)

FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")


@app.after_request
def add_security_headers(response):
    """Baseline headers for production deployments."""
    if not app.config.get("TESTING"):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    return response


@app.errorhandler(Exception)
def handle_unexpected_error(exc):
    """Log server errors without leaking stack traces to clients in production."""
    if isinstance(exc, HTTPException):
        return exc
    logger.exception("Unhandled error: %s", exc)
    if app.config.get("TESTING") or app.debug:
        raise exc
    return jsonify({"status": "error", "error": "Internal server error"}), 500


@app.route("/health")
def health():
    """Liveness check for deployment and monitoring."""
    return jsonify({"status": "ok"})


@app.route("/")
def index():
    """Serve the single-page game shell."""
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.route("/<path:filename>")
def static_files(filename):
    """Serve frontend assets (CSS, JS, etc.)."""
    if not is_safe_static_path(filename):
        abort(404)
    return send_from_directory(FRONTEND_DIR, filename)


@app.route("/api/new-game", methods=["POST"])
@rate_limit(NEW_GAME_LIMITER, "new-game")
def new_game():
    """Start a normal or practice game; returns game_id (never the secret)."""
    data = request.get_json(silent=True) or {}
    if data.get("practice"):
        try:
            game = create_practice_game()
        except GameStoreFullError:
            logger.warning("Game store full on practice new-game")
            return jsonify({"status": "error", "error": "Server busy, try again later"}), 503

        return jsonify(
            {
                "game_id": game.game_id,
                "word_length": WORD_LENGTH,
                "max_attempts": MAX_ATTEMPTS,
                "practice_mode": True,
                "practice_chain": PRACTICE_GUESS_CHAIN,
            }
        )

    try:
        game = create_game()
    except GameStoreFullError:
        logger.warning("Game store full on new-game")
        return jsonify({"status": "error", "error": "Server busy, try again later"}), 503

    return jsonify(
        {
            "game_id": game.game_id,
            "word_length": WORD_LENGTH,
            "max_attempts": MAX_ATTEMPTS,
            "practice_mode": False,
        }
    )


@app.route("/api/guess", methods=["POST"])
@rate_limit(GUESS_LIMITER, "guess")
def guess():
    """Submit a five-letter guess for an active game."""
    data = request.get_json(silent=True) or {}
    game_id = parse_game_id(data.get("game_id"))
    if not game_id:
        return jsonify({"status": "error", "error": "Invalid game_id"}), 400

    normalized_guess = parse_guess(data.get("guess", ""))
    if normalized_guess is None:
        return jsonify({"status": "error", "error": "Guess must be exactly 5 letters"}), 400

    game = get_game(game_id)
    if game is None:
        return jsonify({"status": "error", "error": "Game not found"}), 404

    result = process_guess(game, normalized_guess)

    if result.get("status") == "invalid_word":
        return jsonify(result), 400

    if result.get("status") == "error":
        return jsonify(result), 400

    return jsonify(result)


@app.route("/api/test/new-game", methods=["POST"])
def test_new_game():
    """Create a deterministic game for automated tests (TESTING mode only)."""
    if not app.config.get("TESTING"):
        return jsonify({"status": "error", "error": "Not available"}), 404

    data = request.get_json(silent=True) or {}
    secret = parse_guess(data.get("secret"))
    if secret is None:
        return jsonify({"status": "error", "error": "secret must be a 5-letter word"}), 400

    forced = parse_word_list(data.get("forced_mutations"))
    if forced is None:
        return jsonify({"status": "error", "error": "forced_mutations must be a list of 5-letter words"}), 400

    try:
        game = create_test_game(secret, forced)
    except GameStoreFullError:
        return jsonify({"status": "error", "error": "Server busy, try again later"}), 503

    return jsonify(
        {
            "game_id": game.game_id,
            "word_length": WORD_LENGTH,
            "max_attempts": MAX_ATTEMPTS,
            "practice_mode": False,
        }
    )


if __name__ == "__main__":
    debug = os.getenv("WURDLE_DEBUG", "").lower() in ("1", "true")
    port = int(os.getenv("WURDLE_PORT", "5000"))
    app.run(debug=debug, host=os.getenv("WURDLE_HOST", "127.0.0.1"), port=port)
