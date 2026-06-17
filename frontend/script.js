const API_BASE = window.location.origin;
const WORD_LENGTH = 5;
const MAX_ROWS = 8;

const KEYBOARD_ROWS = [
  ["q", "w", "e", "r", "t", "y", "u", "i", "o", "p"],
  ["a", "s", "d", "f", "g", "h", "j", "k", "l"],
  ["Enter", "z", "x", "c", "v", "b", "n", "m", "Backspace"],
];

const FEEDBACK_LABELS = {
  green: "correct",
  yellow: "present",
  gray: "absent",
};

const KEY_PRIORITY = { green: 3, yellow: 2, gray: 1 };
const MUTATION_KEYBOARD_DELAY_MS = 550;

let gameId = null;
let currentRow = 0;
let currentGuess = "";
let gameOver = false;
let isSubmitting = false;
let stopwatchStartMs = null;
let stopwatchElapsedMs = 0;

const gridEl = document.getElementById("grid");
const knownStateEl = document.getElementById("known-state-row");
const keyboardEl = document.getElementById("keyboard");
const attemptsRemainingEl = document.getElementById("attempts-remaining");
const errorMessageEl = document.getElementById("error-message");
const modalEl = document.getElementById("modal");
const modalTitleEl = document.getElementById("modal-title");
const modalBodyEl = document.getElementById("modal-body");
const modalScoreEl = document.getElementById("modal-score");
const restartBtn = document.getElementById("restart-btn");

function formatStopwatch(ms) {
  const totalSeconds = Math.floor(ms / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  const centiseconds = Math.floor((ms % 1000) / 10);
  return `${minutes}:${String(seconds).padStart(2, "0")}.${String(centiseconds).padStart(2, "0")}`;
}

function startStopwatch() {
  stopwatchStartMs = Date.now();
  stopwatchElapsedMs = 0;
}

function stopStopwatch() {
  if (stopwatchStartMs === null) return 0;
  stopwatchElapsedMs = Date.now() - stopwatchStartMs;
  stopwatchStartMs = null;
  return stopwatchElapsedMs;
}

function resetStopwatch() {
  stopwatchStartMs = null;
  stopwatchElapsedMs = 0;
}

function sanitizeInput(char) {
  return char.toLowerCase().replace(/[^a-z]/g, "");
}

function showError(message) {
  errorMessageEl.textContent = message;
  errorMessageEl.hidden = !message;
}

function clearError() {
  showError("");
}

function createTile(className = "") {
  const tile = document.createElement("div");
  tile.className = `tile ${className}`.trim();
  tile.setAttribute("role", "gridcell");
  tile.setAttribute("aria-label", "empty");
  return tile;
}

function buildGrid() {
  gridEl.innerHTML = "";
  for (let r = 0; r < MAX_ROWS; r++) {
    const row = document.createElement("div");
    row.className = "row";
    row.setAttribute("role", "row");
    row.dataset.row = String(r);
    row.hidden = r > 0;
    for (let c = 0; c < WORD_LENGTH; c++) {
      row.appendChild(createTile());
    }
    gridEl.appendChild(row);
  }
}

function updateVisibleRows() {
  gridEl.querySelectorAll("[data-row]").forEach((row) => {
    row.hidden = Number(row.dataset.row) > currentRow;
  });
}

function scrollToCurrentRow() {
  const row = gridEl.querySelector(`[data-row="${currentRow}"]`);
  if (!row) return;
  row.scrollIntoView({ behavior: "smooth", block: "center" });
}

function buildKnownStateRow() {
  knownStateEl.innerHTML = "";
  for (let c = 0; c < WORD_LENGTH; c++) {
    const tile = createTile();
    tile.textContent = "_";
    tile.setAttribute("aria-label", "unknown position");
    knownStateEl.appendChild(tile);
  }
}

function buildKeyboard() {
  keyboardEl.innerHTML = "";
  KEYBOARD_ROWS.forEach((rowKeys) => {
    const row = document.createElement("div");
    row.className = "keyboard-row";
    rowKeys.forEach((key) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "key";
      if (key === "Enter" || key === "Backspace") {
        btn.classList.add("wide");
      }
      btn.textContent = key === "Backspace" ? "⌫" : key;
      btn.dataset.key = key;
      btn.setAttribute(
        "aria-label",
        key === "Backspace" ? "Backspace" : key === "Enter" ? "Enter guess" : `Letter ${key}`
      );
      btn.addEventListener("click", () => handleKeyPress(key));
      row.appendChild(btn);
    });
    keyboardEl.appendChild(row);
  });
}

function getRowTiles(rowIndex) {
  return gridEl.querySelector(`[data-row="${rowIndex}"]`).children;
}

function renderCurrentGuess() {
  const tiles = getRowTiles(currentRow);
  for (let i = 0; i < WORD_LENGTH; i++) {
    const letter = currentGuess[i] || "";
    tiles[i].textContent = letter.toUpperCase();
    tiles[i].classList.toggle("filled", Boolean(letter));
    tiles[i].setAttribute(
      "aria-label",
      letter ? `letter ${letter}, not submitted` : "empty"
    );
  }
}

function updateKnownState(knownState, lockedPositions) {
  const tiles = knownStateEl.children;
  for (let i = 0; i < WORD_LENGTH; i++) {
    const letter = knownState[i];
    tiles[i].textContent = letter === "_" ? "_" : letter.toUpperCase();
    tiles[i].classList.toggle("locked", lockedPositions[i]);
    tiles[i].setAttribute(
      "aria-label",
      lockedPositions[i]
        ? `locked letter ${letter}`
        : "unknown position"
    );
  }
}

function getKeyColor(keyEl) {
  if (keyEl.classList.contains("green")) return "green";
  if (keyEl.classList.contains("yellow")) return "yellow";
  if (keyEl.classList.contains("gray")) return "gray";
  return null;
}

function getKeyElement(letter) {
  return keyboardEl.querySelector(`[data-key="${letter.toLowerCase()}"]`);
}

function mergeGuessIntoKeyboard(feedback, guess) {
  for (let i = 0; i < WORD_LENGTH; i++) {
    const letter = guess[i];
    const color = feedback[i];
    const key = getKeyElement(letter);
    if (!key) continue;

    const prev = getKeyColor(key);
    if (!prev || KEY_PRIORITY[color] > KEY_PRIORITY[prev]) {
      key.classList.remove("green", "yellow", "gray", "key-stale-yellow");
      key.classList.add(color);
      key.setAttribute("aria-label", `Letter ${letter}, ${FEEDBACK_LABELS[color]}`);
    }
  }
}

function applyKeyboardState(keyboardState = {}, options = {}) {
  const { changedLetters = [], animateStaleYellow = false } = options;
  const changed = new Set(changedLetters.map((l) => l.toLowerCase()));

  keyboardEl.querySelectorAll(".key").forEach((key) => {
    const letter = key.dataset.key;
    if (!letter || letter === "Enter" || letter === "Backspace") return;

    const prev = getKeyColor(key);
    const next = keyboardState[letter] || null;
    const lostYellow =
      animateStaleYellow && prev === "yellow" && next !== "yellow" && next !== "green";

    key.classList.remove("green", "yellow", "gray", "key-updated", "key-stale-yellow");

    if (lostYellow) {
      key.classList.add("key-stale-yellow");
      key.addEventListener(
        "animationend",
        () => {
          key.classList.remove("key-stale-yellow");
          if (next) key.classList.add(next);
        },
        { once: true }
      );
    } else if (next) {
      key.classList.add(next);
    }

    if (prev !== next && (changed.has(letter) || prev !== null)) {
      key.classList.add("key-updated");
      key.addEventListener(
        "animationend",
        () => key.classList.remove("key-updated"),
        { once: true }
      );
    }

    const stateLabel = next ? FEEDBACK_LABELS[next] : "unused";
    key.setAttribute("aria-label", `Letter ${letter}, ${stateLabel}`);
  });
}

function updateKeyboardAfterGuess(data, guess) {
  const postState = data.keyboard_state || {};
  const affected = lettersAffectedByMutation(data);

  mergeGuessIntoKeyboard(data.feedback, guess);

  if (data.mutated_position != null) {
    setTimeout(() => {
      applyKeyboardState(postState, {
        changedLetters: affected,
        animateStaleYellow: true,
      });
    }, MUTATION_KEYBOARD_DELAY_MS);
  } else {
    applyKeyboardState(postState);
  }
}

function lettersAffectedByMutation(data) {
  const letters = new Set();
  if (data.mutated_from) letters.add(data.mutated_from);
  if (data.mutated_to) letters.add(data.mutated_to);
  return [...letters];
}

function applyFeedbackToRow(rowIndex, guess, feedback) {
  const tiles = getRowTiles(rowIndex);
  for (let i = 0; i < WORD_LENGTH; i++) {
    const tile = tiles[i];
    tile.textContent = guess[i].toUpperCase();
    tile.classList.add("filled", feedback[i]);
    tile.setAttribute(
      "aria-label",
      `letter ${guess[i]}, ${FEEDBACK_LABELS[feedback[i]]}`
    );
  }
}

function animateMutation(position) {
  if (position === undefined || position === null) return;
  const tile = knownStateEl.children[position];
  if (!tile) return;
  tile.classList.add("mutating");
  tile.addEventListener(
    "animationend",
    () => tile.classList.remove("mutating"),
    { once: true }
  );
}

function setInputEnabled(enabled) {
  gameOver = !enabled;
  keyboardEl.querySelectorAll("button").forEach((btn) => {
    btn.disabled = !enabled;
  });
}

function showModal(title, body, scoreMs = null) {
  modalTitleEl.textContent = title;
  modalBodyEl.textContent = body;
  if (scoreMs !== null) {
    modalScoreEl.textContent = `Score: ${formatStopwatch(scoreMs)}`;
    modalScoreEl.hidden = false;
  } else {
    modalScoreEl.hidden = true;
    modalScoreEl.textContent = "";
  }
  modalEl.hidden = false;
}

function hideModal() {
  modalEl.hidden = true;
  modalScoreEl.hidden = true;
  modalScoreEl.textContent = "";
}

function resetKeyboardColors() {
  keyboardEl.querySelectorAll(".key").forEach((key) => {
    key.classList.remove("green", "yellow", "gray");
  });
}

function resetUI() {
  currentRow = 0;
  currentGuess = "";
  gameOver = false;
  isSubmitting = false;
  clearError();
  hideModal();
  resetStopwatch();
  resetKeyboardColors();
  buildGrid();
  buildKnownStateRow();
  updateVisibleRows();
  attemptsRemainingEl.textContent = String(MAX_ROWS);
  setInputEnabled(true);
  scrollToCurrentRow();
}

async function apiRequest(path, options = {}) {
  let response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      headers: { "Content-Type": "application/json" },
      ...options,
    });
  } catch {
    throw new Error("Cannot reach the server. Is the backend running?");
  }

  let data;
  try {
    data = await response.json();
  } catch {
    throw new Error("Invalid response from server.");
  }

  if (!response.ok && data.status !== "invalid_word") {
    throw new Error(data.error || "Something went wrong.");
  }

  return data;
}

async function startNewGame() {
  resetUI();
  setInputEnabled(false);
  showError("Starting new game…");

  try {
    const data = await apiRequest("/api/new-game", { method: "POST", body: "{}" });
    gameId = data.game_id;
    attemptsRemainingEl.textContent = String(data.max_attempts);
    clearError();
    startStopwatch();
    setInputEnabled(true);
  } catch (err) {
    showError(err.message);
    setInputEnabled(false);
  }
}

async function submitGuess() {
  if (gameOver || isSubmitting) return;

  if (currentGuess.length < WORD_LENGTH) {
    showError("Not enough letters");
    return;
  }

  isSubmitting = true;
  clearError();

  try {
    const data = await apiRequest("/api/guess", {
      method: "POST",
      body: JSON.stringify({ game_id: gameId, guess: currentGuess }),
    });

    if (data.status === "invalid_word") {
      showError(data.error || "Not in word list");
      isSubmitting = false;
      return;
    }

    applyFeedbackToRow(currentRow, currentGuess, data.feedback);
    updateKeyboardAfterGuess(data, currentGuess);
    updateKnownState(data.known_state, data.locked_positions);
    attemptsRemainingEl.textContent = String(data.attempts_remaining);
    animateMutation(data.mutated_position);

    currentGuess = "";
    currentRow += 1;
    updateVisibleRows();
    scrollToCurrentRow();

    if (data.status === "won") {
      setInputEnabled(false);
      const scoreMs = stopStopwatch();
      showModal(
        "You won!",
        `The word was ${data.secret_word.toUpperCase()}.`,
        scoreMs
      );
    } else if (data.status === "lost") {
      setInputEnabled(false);
      stopStopwatch();
      showModal(
        "Game over",
        `The final secret was ${data.secret_word.toUpperCase()}. Better luck next time!`
      );
    }
  } catch (err) {
    showError(err.message);
  } finally {
    isSubmitting = false;
  }
}

function handleKeyPress(key) {
  if (gameOver || isSubmitting) return;

  if (key === "Enter") {
    submitGuess();
    return;
  }

  if (key === "Backspace") {
    currentGuess = currentGuess.slice(0, -1);
    renderCurrentGuess();
    clearError();
    return;
  }

  const letter = sanitizeInput(key);
  if (!letter || currentGuess.length >= WORD_LENGTH) return;

  currentGuess += letter;
  renderCurrentGuess();
  clearError();
  scrollToCurrentRow();
}

function handlePhysicalKeyboard(event) {
  if (gameOver || isSubmitting) return;

  if (event.key === "Enter") {
    event.preventDefault();
    submitGuess();
    return;
  }

  if (event.key === "Backspace") {
    event.preventDefault();
    currentGuess = currentGuess.slice(0, -1);
    renderCurrentGuess();
    clearError();
    return;
  }

  const letter = sanitizeInput(event.key);
  if (!letter || currentGuess.length >= WORD_LENGTH) return;

  event.preventDefault();
  currentGuess += letter;
  renderCurrentGuess();
  clearError();
  scrollToCurrentRow();
}

restartBtn.addEventListener("click", startNewGame);
document.addEventListener("keydown", handlePhysicalKeyboard);

buildGrid();
buildKnownStateRow();
buildKeyboard();
startNewGame();
