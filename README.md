# Wurdle

A single-player word-guessing game based on Wordle with a twist: after every non-winning guess, one letter of the secret word randomly mutates — but only in positions you haven't locked in with a green tile. You get **8 attempts** instead of the usual 6.

## How to play

1. Guess a valid 5-letter English word and press Enter.
2. Tiles turn **green** (correct spot), **yellow** (in the word, wrong spot), or **gray** (not in the word).
3. Green positions are **locked** and will never mutate again.
4. After each non-winning guess, one unlocked letter in the secret changes — **to another valid dictionary word**.
5. The **known state** row shows locked letters; `_` means that spot can still shift.
6. Win by guessing the current secret exactly; lose if you use all 8 guesses.

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
```

## Run

Start the backend (serves both the API and frontend):

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

## Project structure

```
Wurdle/
  backend/
    app.py              # Flask API + static file serving
    game_logic.py       # Pure game rules (no Flask)
    word_loader.py      # Dictionary loading & validation
    word_lists/
      valid_guesses.txt # ~16k accepted guesses
      answers.txt       # ~2.5k secret words
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
- **Answers** (~1,140 words): common dictionary words suitable as secrets.

Regenerate lists:

```bash
cd backend
python scripts/generate_word_lists.py
```

## Practice run (temporary)

For a scripted demo with a fixed secret and no mutations, start a practice game and type these **8 guesses in order** (one per attempt). **Each word differs from the next by exactly one letter**; all are valid Webster/ENABLE dictionary words:

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

Regenerate a new chain (after updating word lists):

```bash
cd backend
python scripts/prepare_practice_chain.py
python scripts/prepare_practice_chain.py --end bound --write
```

Start practice mode with curl:

```bash
curl -X POST http://localhost:5000/api/new-game \
  -H "Content-Type: application/json" \
  -d "{\"practice\": true}"
```
