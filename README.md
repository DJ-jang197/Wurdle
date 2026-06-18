# Wurdle ;)

A single-player Wordle-style game with a twist: after every non-winning guess, **one letter** of the secret changes — but only in positions you have not locked with a correct (orange) tile. You get the standard **6 attempts** to find the current secret.

The secret always stays a **valid dictionary word**. Mutations move to another valid word one letter at a time (never random gibberish). Which position changes is **random among unlocked slots** — if you lock four letters (orange tiles), only the remaining `_` positions can change. The game avoids reusing past secrets when possible and, when stuck in a small word family, picks the one used longest ago.

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
   - **Yellow clears** only when a **later guess** marks that letter neutral; mutations alone do not recolor keys. Once cleared, yellow does **not** come back for that letter
   - **Amber** — used in your most recent guess with no orange or yellow yet (yellow/orange win over amber)
7. Win by matching the **current** secret exactly. Your **score** is your elapsed time (lower is better). Lose if you use all 6 guesses.

Press **?** (top-right) for the full in-game rules panel.

## Interface

The UI uses the **Freshly Squeezed** palette from Figma (amber `#FFBF00`, pale gold `#F2CF7E`, lemon `#FFE642`, orange `#FF7900`).

| Area | What it does |
|------|----------------|
| **Header** | Title, tagline, attempts remaining |
| **Locked letters** | Shows locked letters in orange; `_` for mutable slots; mutation glow on the slot that changed |
| **Guess grid** | 6 rows with row numbers **1–6**; all rows visible at once; tiles scale so the grid and keyboard fit the viewport |
| **Keyboard** | Orange and yellow persist from guesses; amber highlights letters from your last guess only |
| **? button** | How to play (draggable panel) |
| **Moon / sun** | Light and dark theme |
| **Game-over modal** | Draggable; result, stopwatch score, and **secret word history** (each mutation) |

Light motion: tile **pop** when typing, **yellow fade** on keys when stale yellow clears, smooth **theme** transitions.

## Requirements

- Python 3.10+ (3.14 works)
- A modern web browser

## Setup (one time)

From the **project root** (`Wurdle/`), create a virtual environment and install dependencies:

```powershell
# Windows (PowerShell) — from project root
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt

# For browser tests (first time only)
python -m playwright install chromium
```

```bash
# macOS / Linux — from project root
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium
```

If PowerShell blocks activation (`running scripts is disabled`), run once:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

## Run

**Activate the virtual environment first** — otherwise `python` is your system interpreter and you will see `ModuleNotFoundError: No module named 'flask'`.

```powershell
# Windows (PowerShell) — from project root
.\.venv\Scripts\Activate.ps1
cd backend
python app.py
```

```bash
# macOS / Linux — from project root
source .venv/bin/activate
cd backend
python app.py
```

You should see Flask start on port 5000. Open [http://localhost:5000](http://localhost:5000) in your browser.

**Quick check:** after activating, `python -m pip show flask` should print Flask 3.x. If it says “Package(s) not found”, you are not in the venv or dependencies were not installed.

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

Includes unit tests for game logic, API, word lists, practice chains, security hardening, keyboard yellow clearing, and Playwright checks for viewport layout and keyboard feedback.

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
- **Answers** (~1,140 words): common dictionary words suitable as secrets. Starting secrets must be able to mutate — isolated words with no valid neighbors are excluded. Answer secrets prefer words **not ending in s** for richer mutations (players may still guess any valid word).

Regenerate lists:

```bash
cd backend
python scripts/generate_word_lists.py
```

## Practice mode

For a scripted run with a **fixed secret** and **no mutations**, start practice mode. The API returns an **8-word one-letter chain** as a hint (each step changes exactly one letter; all words are valid). The secret is always **bound** — you still have only **6 guesses**, so use the chain as a guide rather than typing all eight words in order.

Example chain (first six guesses get you to `pound`; you need to reach `bound` within your six attempts):

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
