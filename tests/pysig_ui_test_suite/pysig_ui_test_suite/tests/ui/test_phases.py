import pytest
from playwright.sync_api import expect


pytestmark = pytest.mark.ui


def test_phase_dialog_updates_overlap(loaded_model, model_api):
    page = loaded_model
    page.locator('[data-type="lane"][data-id="A1_1"]').click()
    page.get_by_text("EDIT PHASE DEFINITIONS", exact=True).click()
    expect(page.locator("#phase-dialog")).to_be_visible()
    expect(page.locator(".phase-row")).to_have_count(2)

    phase_a = page.locator('.phase-row[data-phase-id="P_A"]')
    phase_b = page.locator('.phase-row[data-phase-id="P_B"]')

    phase_a.locator('[data-prop="duration_s"]').fill("28")
    phase_a.locator('.phase-signal-groups label', has_text="SG_NS").locator(
        'input[type="checkbox"]'
    ).check()
    phase_b.locator('.phase-signal-groups label', has_text="SG_EW").locator(
        'input[type="checkbox"]'
    ).check()

    page.locator("#apply-phases").click()
    expect(page.locator("#phase-dialog")).to_be_hidden()
    page.locator("#command-input").fill("SAVE")
    page.locator("#command-input").press("Enter")
    page.wait_for_timeout(300)

    model = model_api()
    p_a = next(p for p in model["phases"] if p["id"] == "P_A")
    p_b = next(p for p in model["phases"] if p["id"] == "P_B")
    assert p_a["duration_s"] == 28
    assert "SG_NS" in p_a["active_signal_groups"]
    assert "SG_EW" in p_b["active_signal_groups"]
