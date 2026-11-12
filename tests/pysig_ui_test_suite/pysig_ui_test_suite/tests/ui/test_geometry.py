import pytest
from playwright.sync_api import expect


pytestmark = pytest.mark.ui


def test_entry_and_exit_carriageways_are_offset(loaded_model):
    page = loaded_model
    entry = page.locator('[data-type="lane"][data-id="A1_1"]')
    exit_lane = page.locator('[data-type="lane"][data-id="A3_1"]')
    entry_box = entry.bounding_box()
    exit_box = exit_lane.bounding_box()
    assert entry_box is not None
    assert exit_box is not None
    assert entry_box != exit_box


def test_geometry_handle_drag_changes_arm(loaded_model, model_api):
    page = loaded_model
    page.locator('[data-tool="geometry"]').click()
    handle = page.locator('[data-arm-handle="A1"]')
    expect(handle).to_be_visible()
    box = handle.bounding_box()
    assert box is not None
    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    page.mouse.down()
    page.mouse.move(box["x"] + 20, box["y"] + 60, steps=6)
    page.mouse.up()
    # Save through the command interface before checking persisted API state.
    page.locator("#command-input").fill("SAVE")
    page.locator("#command-input").press("Enter")
    page.wait_for_timeout(300)
    model = model_api()
    arm = next(a for a in model["intersections"][0]["arms"] if a["id"] == "A1")
    assert arm["bearing_degrees"] != 0 or arm["visual_length"] != 270
