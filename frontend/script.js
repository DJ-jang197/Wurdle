/**
 * Wurdle — client-side game UI
 * Talks to the Flask API; renders grid, keyboard, and known-state row.
 */

/* ==========================================================================
   Constants
   ========================================================================== */

const API_BASE = window.location.origin;
const WORD_LENGTH = 5;
const MAX_ROWS = 8;
const THEME_STORAGE_KEY = "wurdle-theme";

const KEYBOARD_ROWS = [
  ["q", "w", "e", "r", "t", "y", "u", "i", "o", "p"],
  ["a", "s", "d", "f", "g", "h", "j", "k", "l"],
  ["Enter", "z", "x", "c", "v", "b", "n", "m", "Backspace"],
];

/** Maps tile/keyboard CSS classes to accessible labels. */
const FEEDBACK_LABELS = {
  green: "correct",
  yellow: "present",
  gray: "absent",
};

/** Wordle-style priority when merging letter colors (higher wins). */
const KEY_PRIORITY = { green: 3, yellow: 2, gray: 1 };

/** Physical keys that must never type into the game. */
const IGNORED_PHYSICAL_KEYS = new Set([
  "Shift",
  "Control",
  "Alt",
  "Meta",
  "Escape",
  "Delete",
  "CapsLock",
  "Tab",
  "Insert",
  "Home",
  "End",
  "PageUp",
  "PageDown",
  "ArrowUp",
  "ArrowDown",
  "ArrowLeft",
  "ArrowRight",
  "F1",
  "F2",
  "F3",
  "F4",
  "F5",
  "F6",
  "F7",
  "F8",
  "F9",
  "F10",
  "F11",
  "F12",
  "ContextMenu",
  "NumLock",
  "ScrollLock",
  "Pause",
  "PrintScreen",
]);

/* ==========================================================================
   State
   ========================================================================== */

let gameId = null;
let currentRow = 0;
let currentGuess = "";
let gameOver = false;
let isSubmitting = false;
let stopwatchStartMs = null;
let stopwatchElapsedMs = 0;
/** Letters from the most recently submitted guess (highlighted until next attempt starts). */
let lastSubmittedLetters = [];
/** Absent letters from the previous guess — faded to neutral on the next submit. */
let previousAbsentLetters = [];

/* ==========================================================================
   DOM references
   ========================================================================== */

const gridScrollEl = document.getElementById("grid-scroll");
const gridEl = document.getElementById("grid");
const knownStateEl = document.getElementById("known-state-row");
const keyboardEl = document.getElementById("keyboard");
const attemptsRemainingEl = document.getElementById("attempts-remaining");
const errorMessageEl = document.getElementById("error-message");
const modalEl = document.getElementById("modal");
const modalCardEl = document.getElementById("modal-card");
const modalDragHandle = document.getElementById("modal-drag-handle");
const modalTitleEl = document.getElementById("modal-title");
const modalBodyEl = document.getElementById("modal-body");
const modalScoreEl = document.getElementById("modal-score");
const modalTimelineEl = document.getElementById("modal-timeline");
const restartBtn = document.getElementById("restart-btn");
const themeToggleBtn = document.getElementById("theme-toggle");
const helpBtn = document.getElementById("help-btn");
const helpPanel = document.getElementById("help-panel");
const helpCloseBtn = document.getElementById("help-close");

/* ==========================================================================
   Theme (light default — Freshly Squeezed palette; dark via toggle)
   ========================================================================== */

/** Apply saved or system-preferred theme on load. */
function initTheme() {
  const saved = localStorage.getItem(THEME_STORAGE_KEY);
  const theme =
    saved === "dark" || saved === "light"
      ? saved
      : window.matchMedia("(prefers-color-scheme: dark)").matches
        ? "dark"
        : "light";
  document.documentElement.setAttribute("data-theme", theme);
  themeToggleBtn.setAttribute(
    "aria-label",
    theme === "dark" ? "Switch to light mode" : "Switch to dark mode"
  );
}

/** Flip between light and dark themes; persist choice. */
function toggleTheme() {
  const next =
    document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark";
  document.documentElement.setAttribute("data-theme", next);
  localStorage.setItem(THEME_STORAGE_KEY, next);
  themeToggleBtn.setAttribute(
    "aria-label",
    next === "dark" ? "Switch to light mode" : "Switch to dark mode"
  );
}

/* ==========================================================================
   Secret stopwatch (score on win only)
   ========================================================================== */

/** Format milliseconds as M:SS.CS for the win modal. */
function formatStopwatch(ms) {
  const totalSeconds = Math.floor(ms / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  const centiseconds = Math.floor((ms % 1000) / 10);
  return `${minutes}:${String(seconds).padStart(2, "0")}.${String(centiseconds).padStart(2, "0")}`;
}

/** Start the hidden timer when a new game begins. */
function startStopwatch() {
  stopwatchStartMs = Date.now();
  stopwatchElapsedMs = 0;
}

/** Stop the timer and return elapsed ms (used as win score). */
function stopStopwatch() {
  if (stopwatchStartMs === null) return 0;
  stopwatchElapsedMs = Date.now() - stopwatchStartMs;
  stopwatchStartMs = null;
  return stopwatchElapsedMs;
}

/** Reset timer state between games. */
function resetStopwatch() {
  stopwatchStartMs = null;
  stopwatchElapsedMs = 0;
}

/* ==========================================================================
   Input helpers
   ========================================================================== */

/** Keep only a single lowercase a–z letter from a key event. */
function sanitizeInput(char) {
  return char.toLowerCase().replace(/[^a-z]/g, "");
}

/** True if this physical key should be ignored entirely. */
function isIgnoredPhysicalKey(event) {
  if (IGNORED_PHYSICAL_KEYS.has(event.key)) return true;
  if (event.ctrlKey || event.altKey || event.metaKey) return true;
  return false;
}

/** Show a red inline error under the grid. */
function showError(message) {
  errorMessageEl.textContent = message;
  errorMessageEl.hidden = !message;
}

/** Clear the inline error message. */
function clearError() {
  showError("");
}

/* ==========================================================================
   Grid & known-state DOM builders
   ========================================================================== */

/** Create one empty tile element for the grid or known-state row. */
function createTile(className = "") {
  const tile = document.createElement("div");
  tile.className = `tile ${className}`.trim();
  tile.setAttribute("role", "gridcell");
  tile.setAttribute("aria-label", "empty");
  return tile;
}

/** Build all 8 guess rows inside the scrollable viewport. */
function buildGrid() {
  gridEl.innerHTML = "";
  for (let r = 0; r < MAX_ROWS; r++) {
    const row = document.createElement("div");
    row.className = "row";
    row.setAttribute("role", "row");
    row.dataset.row = String(r);
    for (let c = 0; c < WORD_LENGTH; c++) {
      row.appendChild(createTile());
    }
    gridEl.appendChild(row);
  }
}

/** Row position inside the scroll container (content coordinates). */
function getRowTopInScroll(rowEl) {
  const containerRect = gridScrollEl.getBoundingClientRect();
  const rowRect = rowEl.getBoundingClientRect();
  return rowRect.top - containerRect.top + gridScrollEl.scrollTop;
}

/** Reset the guess grid scroll position to the top. */
function resetGridScroll() {
  if (!gridScrollEl) return;
  const snapTop = () => {
    gridScrollEl.scrollTop = 0;
  };
  snapTop();
  requestAnimationFrame(() => {
    snapTop();
    requestAnimationFrame(snapTop);
  });
}

/**
 * Scroll only when needed so the current row and the row above are fully visible.
 * Prefers keeping the active row near the bottom without jumping to max scroll.
 */
function scrollToCurrentRow() {
  if (!gridScrollEl) return;

  requestAnimationFrame(() => {
    if (currentRow === 0) {
      gridScrollEl.scrollTop = 0;
      return;
    }

    const prevRowEl = gridEl.querySelector(`[data-row="${currentRow - 1}"]`);
    const currentRowEl = gridEl.querySelector(`[data-row="${currentRow}"]`);
    if (!currentRowEl || gridScrollEl.clientHeight <= 0) return;

    const style = getComputedStyle(gridScrollEl);
    const padTop = parseFloat(style.paddingTop) || 0;
    const padBottom = parseFloat(style.paddingBottom) || 0;
    const viewHeight = gridScrollEl.clientHeight;
    const scrollTop = gridScrollEl.scrollTop;
    const viewBottom = scrollTop + viewHeight;

    const currTop = getRowTopInScroll(currentRowEl);
    const currBottom = currTop + currentRowEl.offsetHeight;
    const prevTop = prevRowEl ? getRowTopInScroll(prevRowEl) : currTop;
    const prevBottom = prevRowEl
      ? prevTop + prevRowEl.offsetHeight
      : currTop;

    const prevFullyVisible =
      !prevRowEl ||
      (prevTop >= scrollTop + padTop - 1 &&
        prevBottom <= viewBottom - padBottom + 1);
    const currFullyVisible =
      currTop >= scrollTop + padTop - 1 &&
      currBottom <= viewBottom - padBottom + 1;

    if (prevFullyVisible && currFullyVisible) return;

    let targetScrollTop = currBottom + padBottom - viewHeight;
    if (prevRowEl && prevTop - padTop < targetScrollTop) {
      targetScrollTop = prevTop - padTop;
    }

    const maxScrollTop = Math.max(0, gridScrollEl.scrollHeight - viewHeight);
    gridScrollEl.scrollTop = Math.min(Math.max(0, targetScrollTop), maxScrollTop);
  });
}

/** Build the five known-state (locked letter) tiles. */
function buildKnownStateRow() {
  knownStateEl.innerHTML = "";
  for (let c = 0; c < WORD_LENGTH; c++) {
    const tile = createTile();
    tile.textContent = "_";
    tile.setAttribute("aria-label", "unknown position");
    knownStateEl.appendChild(tile);
  }
  clearMutationHint();
}

/** Render the on-screen QWERTY keyboard buttons. */
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

/** Return the five tile elements for a guess row index. */
function getRowTiles(rowIndex) {
  return gridEl.querySelector(`[data-row="${rowIndex}"]`).children;
}

/* ==========================================================================
   Grid rendering
   ========================================================================== */

/** Paint the in-progress guess into the active row before submit. */
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

/** Update locked-letter hints from the API known_state array. */
function updateKnownState(knownState, lockedPositions) {
  const tiles = knownStateEl.children;
  for (let i = 0; i < WORD_LENGTH; i++) {
    const letter = knownState[i];
    tiles[i].textContent = letter === "_" ? "_" : letter.toUpperCase();
    tiles[i].classList.toggle("locked", lockedPositions[i]);
    tiles[i].setAttribute(
      "aria-label",
      lockedPositions[i] ? `locked letter ${letter}` : "unknown position"
    );
  }
}

/** Color a submitted guess row from server feedback. */
function applyFeedbackToRow(rowIndex, guess, feedback) {
  const tiles = getRowTiles(rowIndex);
  for (let i = 0; i < WORD_LENGTH; i++) {
    const tile = tiles[i];
    tile.textContent = guess[i].toUpperCase();
    tile.classList.remove("green", "yellow", "gray");
    tile.classList.add("filled", feedback[i]);
    tile.setAttribute(
      "aria-label",
      `letter ${guess[i]}, ${FEEDBACK_LABELS[feedback[i]]}`
    );
  }
}

/** Highlight which secret position changed after the latest wrong guess. */
function highlightMutatedPosition(position) {
  clearMutationHint();
  if (position === undefined || position === null) return;
  const tile = knownStateEl.children[position];
  if (!tile) return;
  tile.classList.add("mutation-hint");
  tile.setAttribute(
    "aria-label",
    `position ${position + 1} changed on last guess`
  );
}

/** Remove mutation glow from all known-state tiles. */
function clearMutationHint() {
  knownStateEl.querySelectorAll(".mutation-hint").forEach((tile) => {
    tile.classList.remove("mutation-hint");
  });
}

/* ==========================================================================
   Keyboard colors — derived from grid tiles so they always match
   ========================================================================== */

/** Read the best color class on a tile (green > yellow > gray). */
function getTileColor(tile) {
  if (tile.classList.contains("green")) return "green";
  if (tile.classList.contains("yellow")) return "yellow";
  if (tile.classList.contains("gray")) return "gray";
  return null;
}

/** Build letter → color map from a single submitted row. */
function buildKeyboardStateFromRow(rowIndex) {
  const state = {};
  const rowEl = gridEl.querySelector(`[data-row="${rowIndex}"]`);
  if (!rowEl) return state;
  const tiles = rowEl.children;
  for (let i = 0; i < WORD_LENGTH; i++) {
    const letter = tiles[i].textContent.trim().toLowerCase();
    const color = getTileColor(tiles[i]);
    if (!letter || !color) continue;
    const prev = state[letter];
    if (!prev || KEY_PRIORITY[color] > KEY_PRIORITY[prev]) {
      state[letter] = color;
    }
  }
  return state;
}

/** Merge grid colors with server state; grid feedback is authoritative. */
function buildFinalKeyboardState(serverState = {}) {
  const final = {};

  // Greens and yellows persist across guesses (Wordle-style).
  for (let r = 0; r <= currentRow; r++) {
    const rowState = buildKeyboardStateFromRow(r);
    for (const [letter, color] of Object.entries(rowState)) {
      if (color === "gray") continue;
      const prev = final[letter];
      if (!prev || KEY_PRIORITY[color] > KEY_PRIORITY[prev]) {
        final[letter] = color;
      }
    }
  }

  // Gray applies only to letters absent in the most recent guess.
  const latestRow = buildKeyboardStateFromRow(currentRow);
  for (const [letter, color] of Object.entries(latestRow)) {
    if (color === "gray" && final[letter] !== "green" && final[letter] !== "yellow") {
      final[letter] = "gray";
    }
  }

  // After a mutation, downgrade stale yellows when the server rescored them gray.
  for (const [letter, serverColor] of Object.entries(serverState)) {
    if (final[letter] === "yellow" && serverColor === "gray") {
      final[letter] = "gray";
    }
  }

  return final;
}

/** Return the current feedback class on a key button, if any. */
function getKeyColor(keyEl) {
  if (keyEl.classList.contains("green")) return "green";
  if (keyEl.classList.contains("yellow")) return "yellow";
  if (keyEl.classList.contains("gray")) return "gray";
  return null;
}

/** Find the on-screen key button for a letter. */
function getKeyElement(letter) {
  return keyboardEl.querySelector(`[data-key="${letter.toLowerCase()}"]`);
}

/**
 * Paint keyboard keys from a letter → color map.
 * Optionally animate keys that lost yellow after a mutation.
 */
function paintKeyboard(state, options = {}) {
  const { animateStaleFor = [], fadeAbsentFor = [] } = options;
  const staleSet = new Set(animateStaleFor.map((l) => l.toLowerCase()));
  const fadeAbsentSet = new Set(fadeAbsentFor.map((l) => l.toLowerCase()));

  keyboardEl.querySelectorAll(".key").forEach((key) => {
    const letter = key.dataset.key;
    if (!letter || letter === "Enter" || letter === "Backspace") return;

    const prev = getKeyColor(key);
    const next = state[letter] || null;
    const shouldFadeYellow =
      staleSet.has(letter) && prev === "yellow" && next !== "yellow" && next !== "green";
    const shouldFadeAbsent =
      fadeAbsentSet.has(letter) && prev === "gray" && next !== "gray";

    key.classList.remove(
      "green",
      "yellow",
      "gray",
      "key-stale-yellow",
      "key-fade-gray",
      "key-updated"
    );
    const keepRecent = key.classList.contains("key-recent");

    if (shouldFadeYellow) {
      key.classList.add("key-stale-yellow");
      key.addEventListener(
        "animationend",
        () => {
          key.classList.remove("key-stale-yellow");
          if (next) key.classList.add(next);
        },
        { once: true }
      );
    } else if (shouldFadeAbsent) {
      key.classList.add("gray", "key-fade-gray");
      key.addEventListener(
        "animationend",
        () => {
          key.classList.remove("key-fade-gray", "gray");
          if (next) key.classList.add(next);
        },
        { once: true }
      );
    } else if (next) {
      key.classList.add(next);
    }

    if (keepRecent) {
      key.classList.add("key-recent");
    }

    const label = next ? FEEDBACK_LABELS[next] : "unused";
    key.setAttribute("aria-label", `Letter ${letter}, ${label}`);
  });
}

/** Letters whose keyboard yellow is removed by the latest server state. */
function findStaleYellowLetters(nextState) {
  const stale = [];
  keyboardEl.querySelectorAll(".key").forEach((key) => {
    const letter = key.dataset.key;
    if (!letter || letter === "Enter" || letter === "Backspace") return;
    if (
      key.classList.contains("yellow") &&
      nextState[letter] !== "yellow" &&
      nextState[letter] !== "green"
    ) {
      stale.push(letter);
    }
  });
  return stale;
}

/** Re-apply amber ring on keys from the last submitted guess. */
function reapplyRecentKeyHighlight() {
  lastSubmittedLetters.forEach((letter) => {
    const key = getKeyElement(letter);
    if (key) key.classList.add("key-recent");
  });
}

/** Strip all feedback colors from keyboard keys (new game). */
function resetKeyboardColors() {
  previousAbsentLetters = [];
  keyboardEl.querySelectorAll(".key").forEach((key) => {
    key.classList.remove(
      "green",
      "yellow",
      "gray",
      "key-stale-yellow",
      "key-fade-gray",
      "key-updated",
      "key-recent"
    );
  });
}

/**
 * After a guess: keyboard matches grid feedback; absent grays fade next round.
 */
function updateKeyboardAfterGuess(data) {
  const finalState = buildFinalKeyboardState(data.keyboard_state || {});
  const fadeAbsent = previousAbsentLetters.filter((letter) => finalState[letter] !== "gray");
  const stale = findStaleYellowLetters(finalState);
  paintKeyboard(finalState, { animateStaleFor: stale, fadeAbsentFor: fadeAbsent });

  previousAbsentLetters = Object.entries(finalState)
    .filter(([, color]) => color === "gray")
    .map(([letter]) => letter);
}

/** Highlight keys from the last submitted guess until the next guess is submitted. */
function highlightRecentKeys(letters) {
  lastSubmittedLetters = [...letters];
  lastSubmittedLetters.forEach((letter) => {
    const key = getKeyElement(letter);
    if (key) key.classList.add("key-recent");
  });
}

/** Clear amber recent-key highlight (new game only). */
function clearRecentKeyHighlight() {
  lastSubmittedLetters = [];
  keyboardEl.querySelectorAll(".key-recent").forEach((key) => {
    key.classList.remove("key-recent");
  });
}

/* ==========================================================================
   Game flow & modals
   ========================================================================== */

/** Enable or disable keyboard input (after win/loss). */
function setInputEnabled(enabled) {
  gameOver = !enabled;
  keyboardEl.querySelectorAll("button").forEach((btn) => {
    btn.disabled = !enabled;
  });
}

/** Render the secret mutation timeline in the game-over dialog. */
function renderSecretTimeline(timeline) {
  if (!timeline || timeline.length === 0) {
    modalTimelineEl.hidden = true;
    modalTimelineEl.innerHTML = "";
    return;
  }

  const items = timeline
    .map((entry) => {
      const word = entry.secret.toUpperCase();
      if (entry.after_attempt === 0) {
        return `<li><strong>Start:</strong> ${word}</li>`;
      }
      const detail =
        entry.mutated_from && entry.mutated_to
          ? ` <span class="mutation-detail">(pos ${entry.mutated_position + 1}: ${entry.mutated_from} → ${entry.mutated_to})</span>`
          : "";
      return `<li><strong>After guess ${entry.after_attempt}:</strong> ${word}${detail}</li>`;
    })
    .join("");

  modalTimelineEl.innerHTML = `<h3>Secret word history</h3><ul>${items}</ul>`;
  modalTimelineEl.hidden = false;
}

/** Reset draggable modal position to default center-top. */
function resetModalPosition() {
  modalCardEl.style.left = "50%";
  modalCardEl.style.top = "18%";
  modalCardEl.style.transform = "translateX(-50%)";
}

/** Allow dragging the game-over card by its handle so the board stays visible. */
function initDraggableModal() {
  let dragging = false;
  let offsetX = 0;
  let offsetY = 0;

  modalDragHandle.addEventListener("pointerdown", (event) => {
    dragging = true;
    modalDragHandle.setPointerCapture(event.pointerId);
    const rect = modalCardEl.getBoundingClientRect();
    offsetX = event.clientX - rect.left;
    offsetY = event.clientY - rect.top;
    modalCardEl.style.transform = "none";
  });

  modalDragHandle.addEventListener("pointermove", (event) => {
    if (!dragging) return;
    modalCardEl.style.left = `${event.clientX - offsetX}px`;
    modalCardEl.style.top = `${event.clientY - offsetY}px`;
  });

  modalDragHandle.addEventListener("pointerup", () => {
    dragging = false;
  });

  modalDragHandle.addEventListener("pointercancel", () => {
    dragging = false;
  });
}

/** Open the how-to-play rules panel. */
function openHelpPanel() {
  helpPanel.hidden = false;
}

/** Close the how-to-play rules panel. */
function closeHelpPanel() {
  helpPanel.hidden = true;
}

/** Show the end-game dialog; include stopwatch score on win and secret timeline. */
function showModal(title, body, options = {}) {
  const { scoreMs = null, secretTimeline = null } = options;
  resetModalPosition();
  modalTitleEl.textContent = title;
  modalBodyEl.textContent = body;
  if (scoreMs !== null) {
    modalScoreEl.textContent = `Score: ${formatStopwatch(scoreMs)}`;
    modalScoreEl.hidden = false;
  } else {
    modalScoreEl.hidden = true;
    modalScoreEl.textContent = "";
  }
  renderSecretTimeline(secretTimeline);
  modalEl.hidden = false;
}

/** Hide the end-game dialog. */
function hideModal() {
  modalEl.hidden = true;
  modalScoreEl.hidden = true;
  modalScoreEl.textContent = "";
  modalTimelineEl.hidden = true;
  modalTimelineEl.innerHTML = "";
}

/** Reset all UI state for a fresh game. */
function resetUI() {
  currentRow = 0;
  currentGuess = "";
  gameOver = false;
  isSubmitting = false;
  lastSubmittedLetters = [];
  clearError();
  hideModal();
  resetStopwatch();
  resetKeyboardColors();
  clearRecentKeyHighlight();
  buildGrid();
  buildKnownStateRow();
  attemptsRemainingEl.textContent = String(MAX_ROWS);
  setInputEnabled(true);
  resetGridScroll();
}

/* ==========================================================================
   API
   ========================================================================== */

/** POST/GET helper with JSON body and basic error handling. */
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

/** Request a new game_id from the server and start the stopwatch. */
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
    resetGridScroll();
    requestAnimationFrame(resetGridScroll);
  } catch (err) {
    showError(err.message);
    setInputEnabled(false);
  }
}

/** Submit the current 5-letter guess to the API and update the board. */
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

    const submittedGuess = currentGuess;

    applyFeedbackToRow(currentRow, submittedGuess, data.feedback);
    updateKeyboardAfterGuess(data);
    highlightRecentKeys(submittedGuess.split(""));
    updateKnownState(data.known_state, data.locked_positions);
    highlightMutatedPosition(data.mutated_position);
    attemptsRemainingEl.textContent = String(data.attempts_remaining);

    currentGuess = "";
    currentRow += 1;
    requestAnimationFrame(() => scrollToCurrentRow());

    if (data.status === "won") {
      setInputEnabled(false);
      const scoreMs = stopStopwatch();
      showModal(
        "You won!",
        `The word was ${data.secret_word.toUpperCase()}.`,
        { scoreMs, secretTimeline: data.secret_timeline }
      );
    } else if (data.status === "lost") {
      setInputEnabled(false);
      stopStopwatch();
      showModal(
        "Game over",
        `The final secret was ${data.secret_word.toUpperCase()}. Better luck next time!`,
        { secretTimeline: data.secret_timeline }
      );
    }
  } catch (err) {
    showError(err.message);
  } finally {
    isSubmitting = false;
  }
}

/* ==========================================================================
   Input handlers (on-screen + physical keyboard)
   ========================================================================== */

/** Handle a click on the virtual keyboard. */
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
}

/** Handle physical keyboard; ignores Shift/Ctrl/Alt/Esc/Delete etc. */
function handlePhysicalKeyboard(event) {
  if (gameOver || isSubmitting) return;
  if (isIgnoredPhysicalKey(event)) return;

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
}

/* ==========================================================================
   Boot
   ========================================================================== */

initTheme();
initDraggableModal();
themeToggleBtn.addEventListener("click", toggleTheme);
helpBtn.addEventListener("click", openHelpPanel);
helpCloseBtn.addEventListener("click", closeHelpPanel);
helpPanel.addEventListener("click", (event) => {
  if (event.target === helpPanel) closeHelpPanel();
});
restartBtn.addEventListener("click", startNewGame);
document.addEventListener("keydown", handlePhysicalKeyboard);

buildGrid();
buildKnownStateRow();
buildKeyboard();
resetGridScroll();
startNewGame();
