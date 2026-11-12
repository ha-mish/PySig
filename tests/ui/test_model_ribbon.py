import pytest
from playwright.sync_api import expect


pytestmark = pytest.mark.ui


@pytest.mark.parametrize(
    "tool",
    ["select", "pan", "arm", "lane", "movement", "geometry", "signal"],
)
def test_model_tool_activates(studio_page, tool):
    button = studio_page.locator(f'[data-tool="{tool}"]')
    expect(button).to_be_visible()
    button.click()
    assert "active" in (button.get_attribute("class") or "").split()


def test_grid_button_toggles_grid(studio_page):
    button = studio_page.locator('[data-action="grid"]')
    grid = studio_page.locator("#grid")
    button.click()
    expect(grid).to_be_hidden()
    button.click()
    expect(grid).to_be_visible()


def test_zoom_and_fit_change_viewbox(studio_page):
    canvas = studio_page.locator("#canvas")
    original = canvas.get_attribute("viewBox")
    studio_page.locator('[data-action="zoom-in"]').click()
    zoomed = canvas.get_attribute("viewBox")
    assert zoomed != original
    studio_page.locator('[data-action="fit"]').click()
    expect(canvas).to_have_attribute("viewBox", "0 0 1400 850")
