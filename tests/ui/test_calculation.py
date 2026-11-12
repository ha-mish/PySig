import pytest
from playwright.sync_api import expect


pytestmark = pytest.mark.ui


def test_run_completes_and_results_are_loaded(loaded_model):
    page = loaded_model
    page.locator('[data-run="run"]').click()
    expect(page.locator("#run-drawer")).to_be_visible()
    expect(page.locator("#calculation-status")).to_have_text(
        "COMPLETE", timeout=60_000
    )
    page.locator('[data-type="lane"][data-id="A1_1"]').click()
    pane = page.locator("#inspector-content")
    expect(pane).to_contain_text("ANALYSIS")
    expect(pane).to_contain_text("Demand")
    expect(pane).to_contain_text("Max queue")
