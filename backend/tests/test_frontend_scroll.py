"""Browser tests for grid scroll behavior (requires playwright)."""

from __future__ import annotations

import threading
import time

import pytest

playwright_sync = pytest.importorskip("playwright.sync_api")
sync_playwright = playwright_sync.sync_playwright

from app import app  # noqa: E402


def _run_server(port: int) -> None:
    app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False)


@pytest.fixture(scope="module")
def live_server_url():
    port = 5055
    thread = threading.Thread(target=_run_server, args=(port,), daemon=True)
    thread.start()
    time.sleep(0.6)
    yield f"http://127.0.0.1:{port}"


def _grid_scroll_top(page) -> float:
    return page.evaluate("() => document.getElementById('grid-scroll').scrollTop")


def _row_tops(page) -> list[float]:
    return page.evaluate(
        """() => {
          const scroller = document.getElementById('grid-scroll');
          const grid = document.getElementById('grid');
          const cRect = scroller.getBoundingClientRect();
          return [...grid.querySelectorAll('.row[data-row]')].map((row) => {
            const r = row.getBoundingClientRect();
            return r.top - cRect.top + scroller.scrollTop;
          });
        }"""
    )


@pytest.fixture
def page(live_server_url):
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 420, "height": 860})
        page.goto(live_server_url)
        page.wait_for_selector("#grid-scroll")
        page.wait_for_function(
            "() => document.getElementById('attempts-remaining')?.textContent === '8'"
        )
        yield page
        browser.close()


def test_grid_starts_at_top(page):
    assert _grid_scroll_top(page) == 0


def test_grid_stays_at_top_after_layout(page):
    page.wait_for_timeout(400)
    assert _grid_scroll_top(page) == 0


def test_scroll_shows_current_and_previous_row(page):
    for word in ("crane", "slate"):
        page.keyboard.type(word)
        page.keyboard.press("Enter")
        page.wait_for_timeout(350)

    scroll_top = _grid_scroll_top(page)
    tops = _row_tops(page)
    prev_top, curr_top = tops[1], tops[2]
    viewport = page.evaluate(
        "() => document.getElementById('grid-scroll').clientHeight"
    )
    prev_bottom = prev_top + page.evaluate(
        "() => document.querySelector('[data-row=\"1\"]').offsetHeight"
    )
    curr_bottom = curr_top + page.evaluate(
        "() => document.querySelector('[data-row=\"2\"]').offsetHeight"
    )

    assert prev_top >= scroll_top - 1
    assert curr_bottom <= scroll_top + viewport + 1
    assert prev_bottom <= scroll_top + viewport + 1
    assert scroll_top < page.evaluate(
        "() => document.getElementById('grid-scroll').scrollHeight"
    )
