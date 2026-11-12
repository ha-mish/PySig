import pytest
from playwright.sync_api import expect


pytestmark = pytest.mark.ui


def test_drag_creates_lane_to_lane_movement(loaded_model, model_api):
    page = loaded_model
    page.locator('[data-tool="movement"]').click()
    origin = page.locator('[data-type="lane"][data-id="A2_1"]')
    destination = page.locator('[data-type="lane"][data-id="A3_1"]')
    origin_box = origin.bounding_box()
    destination_box = destination.bounding_box()
    assert origin_box and destination_box
    page.mouse.move(
        origin_box["x"] + origin_box["width"] / 2,
        origin_box["y"] + origin_box["height"] / 2,
    )
    page.mouse.down()
    expect(page.locator("#movement-preview")).to_be_visible()
    page.mouse.move(
        destination_box["x"] + destination_box["width"] / 2,
        destination_box["y"] + destination_box["height"] / 2,
        steps=8,
    )
    page.mouse.up()
    page.locator("#command-input").fill("SAVE")
    page.locator("#command-input").press("Enter")
    page.wait_for_timeout(300)
    model = model_api()
    assert any(
        m["from_lane_id"] == "A2_1" and m["to_lane_id"] == "A3_1"
        for m in model["movements"]
    )
