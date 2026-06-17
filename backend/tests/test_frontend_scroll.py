"""Browser tests for full-grid layout (requires playwright)."""

from __future__ import annotations

import threading
import time

import pytest

playwright_sync = pytest.importorskip("playwright.sync_api")
sync_playwright = playwright_sync.sync_playwright

from app import app  # noqa: E402


def _run_server(port: int) -> None:
    app.config["TESTING"] = True
    app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False)


@pytest.fixture(scope="module")
def live_server_url():
    port = 5055
    thread = threading.Thread(target=_run_server, args=(port,), daemon=True)
    thread.start()
    time.sleep(0.6)
    yield f"http://127.0.0.1:{port}"


def _layout_metrics(page) -> dict:
    return page.evaluate(
        """() => {
          const app = document.querySelector('.app');
          const gridSection = document.querySelector('.grid-section');
          const keyboard = document.getElementById('keyboard');
          const rows = [...document.querySelectorAll('.row[data-row]')];
          if (!app || !gridSection || !keyboard || rows.length !== 6) {
            return { ok: false, reason: 'missing elements' };
          }
          const appRect = app.getBoundingClientRect();
          const gridRect = gridSection.getBoundingClientRect();
          const kbRect = keyboard.getBoundingClientRect();
          const firstRow = rows[0].getBoundingClientRect();
          const lastRow = rows[5].getBoundingClientRect();
          const overflowY = getComputedStyle(gridSection).overflowY;
          const rowsInsideGrid =
            firstRow.top >= gridRect.top - 1 &&
            lastRow.bottom <= gridRect.bottom + 1;
          const fitsViewport =
            appRect.top <= firstRow.top + 1 &&
            kbRect.bottom <= appRect.bottom + 1;
          return {
            ok: rowsInsideGrid && fitsViewport && overflowY !== 'auto',
            rowsInsideGrid,
            fitsViewport,
            overflowY,
            rowCount: rows.length,
          };
        }"""
    )


@pytest.fixture
def page(live_server_url):
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 420, "height": 860})
        page.goto(live_server_url)
        page.wait_for_selector(".grid-section")
        page.wait_for_function(
            "() => document.getElementById('attempts-remaining')?.textContent === '6'"
        )
        yield page
        browser.close()


def test_all_six_rows_visible_on_load(page):
    metrics = _layout_metrics(page)
    assert metrics["ok"], metrics


def test_layout_stays_fitted_after_guesses(page):
    for word in ("crane", "slate", "crisp"):
        page.keyboard.type(word)
        page.keyboard.press("Enter")
        page.wait_for_timeout(350)

    metrics = _layout_metrics(page)
    assert metrics["ok"], metrics


@pytest.mark.parametrize(
    "viewport",
    [
        {"width": 390, "height": 844},
        {"width": 360, "height": 640},
        {"width": 420, "height": 520},
    ],
)
def test_layout_fits_common_viewports(live_server_url, viewport):
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport=viewport)
        page.goto(live_server_url)
        page.wait_for_selector(".grid-section")
        page.wait_for_timeout(300)
        metrics = _layout_metrics(page)
        browser.close()
    assert metrics["ok"], metrics
