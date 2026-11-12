import pytest
from playwright.sync_api import expect


pytestmark = pytest.mark.ui


def test_entry_lane_shows_signal_information(loaded_model):
    page = loaded_model
    page.locator('[data-type="lane"][data-id="A1_1"]').click()
    pane = page.locator("#inspector-content")
    expect(pane).to_contain_text("SIGNAL CONTROL")
    expect(pane).to_contain_text("C1")
    expect(pane).to_contain_text("SG_EW")
    expect(pane).to_contain_text("T_WE")


def test_exit_lane_does_not_offer_signal_editing(loaded_model):
    page = loaded_model
    page.locator('[data-type="lane"][data-id="A3_1"]').click()
    pane = page.locator("#inspector-content")
    expect(pane).to_contain_text("Exit lane")
    expect(pane.locator(".signal-id-input")).to_have_count(0)


def test_signal_markers_only_appear_on_entry_lanes(loaded_model):
    page = loaded_model
    page.locator('[data-tool="signal"]').click()
    expect(page.locator(".signal-dot")).to_have_count(3)
    # There are three Entry lanes in the fixture and two Exit lanes.


def test_signal_group_can_be_renamed(loaded_model, model_api):
    page = loaded_model
    page.locator('[data-type="lane"][data-id="A1_1"]').click()
    signal = page.locator(".signal-id-input").first
    expect(signal).to_have_value("SG_EW")
    signal.fill("SG_MAIN")
    signal.press("Tab")
    page.locator("#command-input").fill("SAVE")
    page.locator("#command-input").press("Enter")
    page.wait_for_timeout(300)
    model = model_api()
    movement = next(m for m in model["movements"] if m["id"] == "T_WE")
    assert movement["signal_group_id"] == "SG_MAIN"
    phase = next(p for p in model["phases"] if p["id"] == "P_A")
    assert "SG_MAIN" in phase["active_signal_groups"]
    assert "SG_EW" not in phase["active_signal_groups"]
