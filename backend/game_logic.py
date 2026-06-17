"""Pure game logic for Wurdle — no web framework dependencies."""

from __future__ import annotations

import random
import string
import uuid
from dataclasses import dataclass, field
from typing import Literal

from word_loader import is_valid_guess, pick_random_answer

WORD_LENGTH = 5
MAX_ATTEMPTS = 8

Feedback = Literal["green", "yellow", "gray"]
GameStatus = Literal["in_progress", "won", "lost"]

_games: dict[str, "GameState"] = {}


def score_guess(secret: str, guess: str) -> list[Feedback]:
    """Score a guess against the secret using standard Wordle rules."""
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


def mutate(secret: str, locked: list[bool]) -> tuple[str, int]:
    """Mutate one unlocked position to a different letter."""
    unlocked = [i for i in range(WORD_LENGTH) if not locked[i]]
    if not unlocked:
        raise ValueError("No unlocked positions to mutate")

    index = random.choice(unlocked)
    current = secret[index]
    alphabet = [c for c in string.ascii_lowercase if c != current]
    new_letter = random.choice(alphabet)
    new_secret = secret[:index] + new_letter + secret[index + 1 :]
    return new_secret, index


def build_known_state(secret: str, locked: list[bool]) -> list[str]:
    return [secret[i] if locked[i] else "_" for i in range(WORD_LENGTH)]


_FEEDBACK_PRIORITY = {"green": 3, "yellow": 2, "gray": 1}


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
        for i, letter in enumerate(guess):
            color = feedback[i]
            current = state.get(letter)
            if current is None or _FEEDBACK_PRIORITY[color] > _FEEDBACK_PRIORITY[current]:
                state[letter] = color

    return state


@dataclass
class GameState:
    game_id: str
    secret: str
    locked: list[bool] = field(default_factory=lambda: [False] * WORD_LENGTH)
    attempts_used: int = 0
    status: GameStatus = "in_progress"
    guess_history: list[str] = field(default_factory=list)

    def apply_guess(self, guess: str) -> dict:
        """Process a guess and return the API response payload."""
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
        else:
            keyboard_pre_mutation = compute_keyboard_state(
                self.secret, self.guess_history, self.locked
            )
            self.secret, mutated_position = mutate(self.secret, self.locked)

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

        if self.status in ("won", "lost"):
            response["secret_word"] = self.secret

        return response


def create_game() -> GameState:
    game_id = str(uuid.uuid4())
    game = GameState(game_id=game_id, secret=pick_random_answer())
    _games[game_id] = game
    return game


def get_game(game_id: str) -> GameState | None:
    return _games.get(game_id)


def process_guess(game: GameState, guess: str) -> dict:
    return game.apply_guess(guess)


def new_game() -> GameState:
    """Alias for create_game (used in tests)."""
    return create_game()


def clear_games() -> None:
    """Clear in-memory game store (for tests)."""
    _games.clear()
