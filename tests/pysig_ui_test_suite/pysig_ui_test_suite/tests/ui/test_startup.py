import pytest
from playwright.sync_api import expect


pytestmark = pytest.mark.ui


def test_studio_shell_is_visible(studio_page):
    page = studio_page
    expect(page.locator(".menu-bar")).to_be_visible()
    expect(page.locator(".tool-strip")).to_be_visible()
    expect(page.locator("#canvas")).to_be_visible()
    expect(page.locator(".inspector")).to_be_visible()
    expect(page.locator("#command-input")).to_be_editable()
    expect(page.locator(".status-bar")).to_be_visible()


def test_command_interface_responds(studio_page):
    entry = studio_page.locator("#command-input")
    entry.fill("HELP")
    entry.press("Enter")
    expect(studio_page.locator("#command-history")).to_contain_text("ARM ADD")


def test_startup_has_no_browser_errors(studio_page, browser_errors):
    assert browser_errors == []
