# Wurdle ;)

A single-player Wordle-style game with a twist: after every non-winning guess, **one letter** of the secret changes — but only in positions you have not locked with a correct (orange) tile. You get **8 attempts** instead of the usual 6.

The secret always stays a **valid dictionary word**. Mutations move to another valid word one letter at a time (never random gibberish). Which position changes is **random** among all legal one-letter moves at unlocked slots — not tied to your last guess.

## How to play

1. Guess a **5-letter** English word and press **Enter** (or use the on-screen keyboard).
2. **Grid tile colors** (frozen per row when you submit):
   - **Orange** — correct letter, correct spot (locks that position)
   - **Yellow** — in the word, wrong spot
   - **Pale gold** — not in the word for that guess
3. **Orange locks a letter.** Locked letters appear in orange in the **Locked letters** row above the grid; `_` means that spot can still change.
4. After each wrong guess, **one unlocked letter** in the secret mutates to another valid word. A **glow** on the locked row shows which position changed.
5. Because the secret can shift, feedback on old rows stays as it was when you played them — but the **current** secret is what matters for winning.
6. **Keyboard colors** (separate from grid tiles):
   - **Orange / yellow** — best feedback so far from past guesses (no pale gold on keys)
   - **Yellow clears** when a later guess marks that letter neutral, or when a mutation removes it from the secret; once cleared, yellow does **not** come back for that letter
   - **Amber** — used in your most recent guess with no orange or yellow yet (yellow/orange win over amber)
7. Win by matching the **current** secret exactly. Your **score** is your elapsed time (lower is better). Lose if you use all 8 guesses.

Press **?** (top-right) for the full in-game rules panel.

## Interface

The UI uses the **Freshly Squeezed** palette (amber `#FFBF00`, pale gold `#F2CF7E`, lemon `#FFE642`, orange `#FF7900`).

| Area | What it does |
|------|----------------|
| **Header** | Title, tagline, attempts remaining |
| **Locked letters** | Shows locked letters in orange; `_` for mutable slots; mutation glow on the slot that changed |
| **Guess grid** | 8 rows with row numbers **1–8**; scroll area fits **5 rows** at a time |
| **Keyboard** | Orange and yellow persist from guesses; amber highlights letters from your last guess only |
| **? button** | How to play (draggable panel) |
| **Moon / sun** | Light and dark theme |
| **Game-over modal** | Draggable; result, stopwatch score, and **secret word history** (each mutation) |

Light motion: tile **pop** when typing, **yellow fade** on keys when stale yellow clears, smooth **theme** transitions.

## Requirements

- Python 3.10+
- A modern web browser

## Setup

```bash
# From the project root
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt

# For browser tests (first time only)
python -m playwright install chromium
```

## Run

Start the server (serves the API and frontend):

```bash
cd backend
python app.py
```

Open [http://localhost:5000](http://localhost:5000) in your browser.

For production, copy `.env.example` to `.env`, set `WURDLE_DEBUG=false`, bind behind HTTPS (reverse proxy), and optionally set `WURDLE_CORS_ORIGINS` to your site origin. Use a WSGI server (e.g. gunicorn) instead of `app.run` for real deployments.

## Security

This app has **no user accounts** — games are anonymous and keyed by `game_id` only. Built-in protections:

| Control | Behavior |
|---------|----------|
| **Input validation** | `game_id` must be a UUID; guesses must be exactly 5 letters |
| **Rate limiting** | Per-IP limits on `/api/new-game` and `/api/guess` (disabled in tests) |
| **Game store cap** | Max in-memory games with TTL cleanup for abandoned/finished games |
| **Secret handling** | `secret_word` only returned on win or loss |
| **Test API** | `/api/test/new-game` only when `WURDLE_TESTING=true` |
| **Static files** | Only known frontend extensions; path traversal blocked |
| **Headers** | `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy` in production |

Tune limits via `.env` (see `.env.example`).

## Run tests

```bash
cd backend
pytest
```

Includes unit tests for game logic, API, word lists, practice chains, security hardening, keyboard yellow clearing, and Playwright checks for grid scroll and keyboard feedback.

## API

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Liveness check |
| `POST` | `/api/new-game` | Start a game (`{"practice": true}` for practice mode) |
| `POST` | `/api/guess` | Submit a guess (`game_id`, `guess`) |

The secret is never returned until the game ends (win or loss). Guess responses include `feedback`, `locked_positions`, `known_state`, `keyboard_state`, and mutation fields when applicable.

## Project structure

```
Wurdle/
  backend/
    app.py                    # Flask server + static frontend
    security.py               # Validation, rate limits, static path checks
    game_logic.py             # Scoring, locking, mutation, game state
    practice_chain.py         # One-letter practice chain finder
    word_loader.py            # Dictionary loading & validation
    word_lists/
      valid_guesses.txt       # ~8,600 accepted guesses
      answers.txt             # ~1,140 secret words
    scripts/
      generate_word_lists.py  # Regenerate lists from ENABLE
      prepare_practice_chain.py
      find_practice_chain.py
    tests/
  frontend/
    index.html
    style.css
    script.js
  requirements.txt
  README.md
```

## Word lists

- **Valid guesses** (~8,600 words): 5-letter words from the [ENABLE](https://github.com/dolph/dictionary) dictionary (Merriam-Webster Scrabble word list).
- **Names, regions, and proper nouns** are filtered out (e.g. `china`, `texas`, `paris`).
- **Answers** (~1,140 words): common dictionary words suitable as secrets. Starting secrets must be able to mutate — isolated words with no valid neighbors are excluded.

Regenerate lists:

```bash
cd backend
python scripts/generate_word_lists.py
```

## Practice mode

For a scripted run with a **fixed secret** and **no mutations**, start practice mode and type these **8 guesses in order** (one per attempt). Each word differs from the next by **exactly one letter**; all are valid dictionary words:

| # | Guess |
|---|-------|
| 1 | could |
| 2 | would |
| 3 | wound |
| 4 | sound |
| 5 | round |
| 6 | pound |
| 7 | found |
| 8 | **bound** |

The secret is always **bound** — you win on the 8th guess.

Regenerate or write a new chain (after updating word lists):

```bash
cd backend
python scripts/prepare_practice_chain.py
python scripts/prepare_practice_chain.py --end bound --write
```

Start practice mode:

```bash
curl -X POST http://localhost:5000/api/new-game \
  -H "Content-Type: application/json" \
  -d "{\"practice\": true}"
```

Use the returned `game_id` with `POST /api/guess` as in a normal game.
