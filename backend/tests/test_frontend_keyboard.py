"""Browser tests for keyboard feedback (requires playwright)."""

from __future__ import annotations

import threading
import time
from pathlib import Path

import pytest

playwright_sync = pytest.importorskip("playwright.sync_api")
sync_playwright = playwright_sync.sync_playwright

from app import app  # noqa: E402

SNAPSHOT_DIR = Path(__file__).parent / "snapshots" / "keyboard"


def _run_server(port: int) -> None:
    app.config["TESTING"] = True
    app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False)


@pytest.fixture(scope="module")
def live_server_url():
    port = 5056
    thread = threading.Thread(target=_run_server, args=(port,), daemon=True)
    thread.start()
    time.sleep(0.6)
    yield f"http://127.0.0.1:{port}"


@pytest.fixture
def page(live_server_url):
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 420, "height": 860})
        page.goto(f"{live_server_url}/?test=1")
        page.wait_for_selector("#keyboard")
        page.wait_for_function("() => typeof window.__wurdleTest !== 'undefined'")
        yield page
        browser.close()


def _bind_test_game(page, secret: str, forced_mutations: list[str] | None = None) -> str:
    game = page.evaluate(
        """async ([secret, forcedMutations]) => {
          const res = await fetch('/api/test/new-game', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ secret, forced_mutations: forcedMutations || [] }),
          });
          return res.json();
        }""",
        [secret, forced_mutations or []],
    )
    page.evaluate("(id) => window.__wurdleTest.bindGame(id)", game["game_id"])
    return game["game_id"]


def _submit_word(page, word: str) -> None:
    page.keyboard.type(word)
    page.keyboard.press("Enter")
    page.wait_for_timeout(450)


def _key_classes(page, letter: str) -> list[str]:
    return page.evaluate(
        "(letter) => window.__wurdleTest.keyClasses(letter)",
        letter,
    )


def test_sauce_space_clears_a_yellow_keeps_amber(page):
    _bind_test_game(page, "learn", ["blend"])
    _submit_word(page, "sauce")
    _submit_word(page, "space")

    a_classes = _key_classes(page, "a")
    assert "yellow" not in a_classes
    assert "green" not in a_classes
    assert "key-recent" in a_classes

    page.locator(".keyboard").screenshot(
        path=SNAPSHOT_DIR / "sauce-space-a-neutral.png"
    )


def test_stale_yellow_clears_r_after_secret_mutates(page, live_server_url):
    _bind_test_game(page, "dream", ["cease"])
    _submit_word(page, "realm")
    _submit_word(page, "reads")

    r_classes = _key_classes(page, "r")
    assert "yellow" not in r_classes
    assert "green" not in r_classes

    e_classes = _key_classes(page, "e")
    assert "green" in e_classes or "yellow" in e_classes

    page.locator(".keyboard").screenshot(
        path=SNAPSHOT_DIR / "stale-yellow-r-cleared.png"
    )


def test_yellow_stays_when_letter_remains_in_secret(page):
    _bind_test_game(page, "dream", ["dread"])
    _submit_word(page, "realm")

    r_classes = _key_classes(page, "r")
    assert "yellow" in r_classes
    assert "key-recent" not in r_classes

    page.locator(".keyboard").screenshot(
        path=SNAPSHOT_DIR / "yellow-r-kept.png"
    )


def test_orange_not_cleared_by_mutation(page):
    _bind_test_game(page, "dream", ["cease"])
    _submit_word(page, "realm")

    m_classes = _key_classes(page, "m")
    assert "green" in m_classes

    page.locator(".keyboard").screenshot(
        path=SNAPSHOT_DIR / "orange-m-kept.png"
    )


def test_amber_only_on_latest_guess(page):
    _bind_test_game(page, "dream", ["cease"])
    _submit_word(page, "realm")
    _submit_word(page, "reads")

    assert "key-recent" in _key_classes(page, "r")
    assert "key-recent" not in _key_classes(page, "l")


def test_s_yellow_cleared_permanently_after_gray_row(page):
    _bind_test_game(page, "mesas", ["apple", "mesas"])
    _submit_word(page, "storm")
    assert "yellow" in _key_classes(page, "s")

    _submit_word(page, "sheep")
    assert "yellow" not in _key_classes(page, "s")

    _submit_word(page, "storm")
    assert "yellow" not in _key_classes(page, "s")

    page.locator(".keyboard").screenshot(
        path=SNAPSHOT_DIR / "s-yellow-permanently-cleared.png"
    )
