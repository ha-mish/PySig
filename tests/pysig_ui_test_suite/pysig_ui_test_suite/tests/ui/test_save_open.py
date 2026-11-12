import pytest
from playwright.sync_api import expect


pytestmark = pytest.mark.ui


def test_save_and_reopen_round_trip(loaded_model):
    page = loaded_model
    page.locator('[data-type="lane"][data-id="A1_1"]').click()
    length = page.locator('.property-row', has_text="Length m").locator("input")
    length.fill("231")
    length.press("Tab")
    page.locator("#command-input").fill("SAVE")
    page.locator("#command-input").press("Enter")
    expect(page.locator("#saved-state")).to_have_text("SAVED")

    page.get_by_text("Open", exact=True).first.click()
    page.locator("#config-list").select_option("ui_feature_test.yaml")
    page.locator("#confirm-open").click()
    page.locator('[data-type="lane"][data-id="A1_1"]').click()
    expect(
        page.locator('.property-row', has_text="Length m").locator("input")
    ).to_have_value("231")
