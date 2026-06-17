# Wurdle ;)

A single-player Wordle-style game with a twist: after every non-winning guess, **one letter** of the secret changes — but only in positions you have not locked with a correct (orange) tile. You get **8 attempts** instead of the usual 6.

The secret always stays a **valid dictionary word**. Mutations move to another valid word one letter at a time (never random gibberish).

## How to play

1. Guess a **5-letter** English word and press **Enter** (or use the on-screen keyboard).
2. Tile colors on the grid:
   - **Orange** — correct letter, correct spot (locks that position)
   - **Yellow** — in the word, wrong spot
   - **Brown** — not in the word for that guess
3. **Orange locks a letter.** Locked letters appear in the row above the grid; `_` means that spot can still change.
4. After each wrong guess, **one unlocked letter** in the secret mutates to another valid word. A **glowing slot** in the locked row shows which position changed.
5. Because the secret can shift, a letter marked “not in word” on one turn may work on a later turn.
6. Win by matching the **current** secret exactly. Your **score** is your elapsed time (lower is better). Lose if you use all 8 guesses.

Press **?** (top-right) for the full in-game rules panel.

## Interface

The UI uses the **Freshly Squeezed** palette (amber `#FFBF00`, pale gold `#F2CF7E`, lemon `#FFE642`, orange `#FF7900`).

| Area | What it does |
|------|----------------|
| **Header** | Title, tagline, attempts remaining |
| **Locked letters** | Known locked positions; mutation hint glows on the slot that changed |
| **Guess grid** | 8 rows with subtle row numbers **1–8**; scroll area shows **5 rows** at a time and starts at the top |
| **Keyboard** | Orange / yellow from earlier guesses; **warm gold** = not in word on your **last guess only** (fades next turn); **ring outline** = letters you just submitted |
| **? button** | How to play |
| **Moon / sun** | Light and dark theme |
| **Game-over modal** | Draggable; shows result, stopwatch score, and **secret word history** (each mutation) |

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

# For browser scroll/layout tests (first time only)
python -m playwright install chromium
```

## Run

Start the server (serves the API and frontend):

```bash
cd backend
python app.py
```

Open [http://localhost:5000](http://localhost:5000) in your browser.

## Run tests

```bash
cd backend
pytest
```

Includes unit tests for game logic, API, word lists, practice chains, and Playwright checks for grid scroll behavior.

## Project structure

```
Wurdle/
  backend/
    app.py                    # Flask server + static frontend
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

## Practice run (temporary, API only)

For a scripted demo with a **fixed secret** and **no mutations**, start a practice game and type these **8 guesses in order** (one per attempt). Each word differs from the next by **exactly one letter**; all are valid dictionary words:

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
