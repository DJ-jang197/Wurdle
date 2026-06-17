"""Pure game logic for Wurdle — no web framework dependencies."""

from __future__ import annotations

import os
import random
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal

from word_loader import get_answers, get_valid_guesses, is_valid_guess, pick_random_answer, without_plural_s_endings
from practice_chain import PRACTICE_ANSWER, PRACTICE_GUESS_CHAIN, mutation_options

WORD_LENGTH = 5
MAX_ATTEMPTS = 6

GAME_TTL_SECONDS = int(os.getenv("WURDLE_GAME_TTL_HOURS", "24")) * 3600
FINISHED_GAME_TTL_SECONDS = int(os.getenv("WURDLE_FINISHED_TTL_HOURS", "2")) * 3600
MAX_GAMES = int(os.getenv("WURDLE_MAX_GAMES", "5000"))

Feedback = Literal["green", "yellow", "gray"]
GameStatus = Literal["in_progress", "won", "lost"]

_games: dict[str, "GameState"] = {}


class GameStoreFullError(Exception):
    """Raised when the in-memory game store cannot accept more games."""


def score_guess(secret: str, guess: str) -> list[Feedback]:
    """Score a guess using standard Wordle rules (including duplicate letters).

    Each letter in the secret can only produce one green or yellow response.
    Extra copies of a letter in the guess are gray. Greens are matched first,
    then yellows consume remaining secret letter counts left to right.
    """
    secret = secret.lower()
    guess = guess.lower()
    result: list[Feedback] = ["gray"] * WORD_LENGTH
    secret_counts: dict[str, int] = {}

    for i in range(WORD_LENGTH):
        if guess[i] == secret[i]:
            result[i] = "green"
        else:
            secret_counts[secret[i]] = secret_counts.get(secret[i], 0) + 1

    for i in range(WORD_LENGTH):
        if result[i] == "green":
            continue
        letter = guess[i]
        if secret_counts.get(letter, 0) > 0:
            result[i] = "yellow"
            secret_counts[letter] -= 1

    return result


def _steps_since_last_use(word: str, history: list[str]) -> int:
    """How many secrets ago this word was last used (larger = longer ago)."""
    if word not in history:
        return len(history) + 1
    return len(history) - 1 - history[::-1].index(word)


def _prefer_without_s_endings(options: list[tuple[str, int]]) -> list[tuple[str, int]]:
    """Drop s-ending words when other mutation targets exist."""
    non_s = [(word, index) for word, index in options if not word.endswith("s")]
    return non_s if non_s else options


def _collect_mutation_options(secret: str, locked: list[bool]) -> list[tuple[str, int]]:
    """Legal one-letter moves; answer words first, then extra valid-guess neighbors."""
    answers = without_plural_s_endings(get_answers())
    options = mutation_options(secret, locked, answers)
    guesses = get_valid_guesses()
    if not options:
        options = _prefer_without_s_endings(mutation_options(secret, locked, guesses))
        return options

    seen = {word for word, _ in options}
    for word, index in mutation_options(secret, locked, guesses):
        if word not in seen:
            options.append((word, index))
            seen.add(word)
    return _prefer_without_s_endings(options)


def _pick_mutation(
    options: list[tuple[str, int]],
    *,
    current: str,
    avoid_secrets: frozenset[str],
    secret_history: list[str],
) -> tuple[str, int]:
    """Prefer unused secrets, then words used longest ago; never pick current if avoidable."""
    fresh = [(word, index) for word, index in options if word not in avoid_secrets]
    pool = fresh if fresh else list(options)

    without_current = [(word, index) for word, index in pool if word != current]
    if without_current:
        pool = without_current

    best_gap = max(_steps_since_last_use(word, secret_history) for word, _ in pool)
    candidates = [
        (word, index)
        for word, index in pool
        if _steps_since_last_use(word, secret_history) == best_gap
    ]
    return random.choice(_prefer_without_s_endings(candidates))


def mutate(
    secret: str,
    locked: list[bool],
    avoid_secrets: frozenset[str] | None = None,
    secret_history: list[str] | None = None,
) -> tuple[str, int]:
    """Mutate one unlocked position; diversify away from recent secrets."""
    history = list(secret_history or [])
    avoid = avoid_secrets if avoid_secrets is not None else frozenset(history)
    options = _collect_mutation_options(secret, locked)
    if not options:
        raise ValueError(f"No valid dictionary mutation from {secret!r} with locked={locked}")

    return _pick_mutation(
        options,
        current=secret,
        avoid_secrets=avoid,
        secret_history=history,
    )


def build_known_state(secret: str, locked: list[bool]) -> list[str]:
    """Return locked letters and '_' for positions still able to mutate."""
    return [secret[i] if locked[i] else "_" for i in range(WORD_LENGTH)]


_FEEDBACK_PRIORITY = {"green": 3, "yellow": 2, "gray": 1}


def merge_keyboard_feedback(
    state: dict[str, Feedback], guess: str, feedback: list[Feedback]
) -> None:
    """Merge one row into keyboard state; best color wins per letter (not per tile)."""
    for i, letter in enumerate(guess.lower()):
        color = feedback[i]
        current = state.get(letter)
        if current is None or _FEEDBACK_PRIORITY[color] > _FEEDBACK_PRIORITY[current]:
            state[letter] = color


def compute_keyboard_state(
    secret: str, guesses: list[str], locked: list[bool]
) -> dict[str, Feedback]:
    """Keyboard colors from current secret — updates when the secret mutates."""
    state: dict[str, Feedback] = {}

    for i, is_locked in enumerate(locked):
        if is_locked:
            state[secret[i]] = "green"

    for guess in guesses:
        feedback = score_guess(secret, guess)
        merge_keyboard_feedback(state, guess, feedback)

    return state


@dataclass
class GameState:
    """In-memory state for one active Wurdle game."""

    game_id: str
    secret: str
    locked: list[bool] = field(default_factory=lambda: [False] * WORD_LENGTH)
    attempts_used: int = 0
    status: GameStatus = "in_progress"
    guess_history: list[str] = field(default_factory=list)
    secret_timeline: list[dict] = field(default_factory=list)
    practice_mode: bool = False
    forced_mutations: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def touch(self) -> None:
        """Record last access time (for TTL pruning)."""
        self.updated_at = datetime.now(timezone.utc)

    def apply_guess(self, guess: str) -> dict:
        """Process a guess and return the API response payload."""
        self.touch()
        if self.status != "in_progress":
            return {
                "status": "error",
                "error": "Game is already over",
            }

        normalized = guess.strip().lower()
        if not is_valid_guess(normalized):
            return {
                "status": "invalid_word",
                "error": "Not in word list",
            }

        feedback = score_guess(self.secret, normalized)
        self.attempts_used += 1
        self.guess_history.append(normalized)

        for i, color in enumerate(feedback):
            if color == "green":
                self.locked[i] = True

        mutated_position: int | None = None
        previous_secret = self.secret
        keyboard_pre_mutation: dict[str, Feedback] | None = None

        if all(c == "green" for c in feedback):
            self.status = "won"
        elif self.attempts_used >= MAX_ATTEMPTS:
            self.status = "lost"
        elif not self.practice_mode:
            keyboard_pre_mutation = compute_keyboard_state(
                self.secret, self.guess_history, self.locked
            )
            if self.forced_mutations:
                previous_secret = self.secret
                self.secret = self.forced_mutations.pop(0)
                mutated_position = next(
                    (
                        i
                        for i in range(WORD_LENGTH)
                        if not self.locked[i] and previous_secret[i] != self.secret[i]
                    ),
                    None,
                )
            else:
                secret_history = [entry["secret"] for entry in self.secret_timeline]
                self.secret, mutated_position = mutate(
                    self.secret,
                    self.locked,
                    frozenset(secret_history),
                    secret_history,
                )

        keyboard_state = compute_keyboard_state(
            self.secret, self.guess_history, self.locked
        )

        response: dict = {
            "status": self.status,
            "feedback": feedback,
            "locked_positions": list(self.locked),
            "known_state": build_known_state(self.secret, self.locked),
            "keyboard_state": keyboard_state,
            "attempts_used": self.attempts_used,
            "attempts_remaining": MAX_ATTEMPTS - self.attempts_used,
        }

        if keyboard_pre_mutation is not None:
            response["keyboard_state_pre_mutation"] = keyboard_pre_mutation

        if mutated_position is not None:
            response["mutated_from"] = previous_secret[mutated_position]
            response["mutated_to"] = self.secret[mutated_position]

        if mutated_position is not None:
            response["mutated_position"] = mutated_position
            self.secret_timeline.append(
                {
                    "after_attempt": self.attempts_used,
                    "secret": self.secret,
                    "mutated_position": mutated_position,
                    "mutated_from": previous_secret[mutated_position],
                    "mutated_to": self.secret[mutated_position],
                }
            )

        if self.status in ("won", "lost"):
            response["secret_word"] = self.secret
            response["secret_timeline"] = list(self.secret_timeline)

        return response


def prune_stale_games() -> int:
    """Remove finished and abandoned games past TTL. Returns count removed."""
    now = datetime.now(timezone.utc)
    expired: list[str] = []
    for game_id, game in _games.items():
        age = (now - game.updated_at).total_seconds()
        if game.status != "in_progress":
            if age > FINISHED_GAME_TTL_SECONDS:
                expired.append(game_id)
        elif age > GAME_TTL_SECONDS:
            expired.append(game_id)
    for game_id in expired:
        del _games[game_id]
    return len(expired)


def _register_game(game: GameState) -> None:
    """Store a new game after pruning stale entries and checking capacity."""
    prune_stale_games()
    if len(_games) >= MAX_GAMES:
        raise GameStoreFullError("Server busy, try again later")
    _games[game.game_id] = game


def create_game() -> GameState:
    """Create a new standard game with a random mutable secret."""
    game_id = str(uuid.uuid4())
    secret = pick_random_answer()
    game = GameState(game_id=game_id, secret=secret)
    game.secret_timeline.append({"after_attempt": 0, "secret": secret})
    _register_game(game)
    return game


def create_practice_game() -> GameState:
    """Scripted practice game: fixed secret, no mutations, win on the 8th chain word."""
    game_id = str(uuid.uuid4())
    game = GameState(
        game_id=game_id,
        secret=PRACTICE_ANSWER,
        practice_mode=True,
    )
    game.secret_timeline.append({"after_attempt": 0, "secret": PRACTICE_ANSWER})
    _register_game(game)
    return game


def create_test_game(secret: str, forced_mutations: list[str] | None = None) -> GameState:
    """Deterministic game for automated tests (forced mutation queue optional)."""
    game_id = str(uuid.uuid4())
    normalized_secret = secret.lower()
    game = GameState(
        game_id=game_id,
        secret=normalized_secret,
        forced_mutations=[word.lower() for word in (forced_mutations or [])],
    )
    game.secret_timeline.append({"after_attempt": 0, "secret": normalized_secret})
    _register_game(game)
    return game


def get_game(game_id: str) -> GameState | None:
    """Look up an active game by id, or None if missing."""
    return _games.get(game_id)


def process_guess(game: GameState, guess: str) -> dict:
    """Apply a guess to a game and return the API response payload."""
    return game.apply_guess(guess)


def new_game() -> GameState:
    """Alias for create_game (used in tests)."""
    return create_game()


def clear_games() -> None:
    """Clear in-memory game store (for tests)."""
    _games.clear()
