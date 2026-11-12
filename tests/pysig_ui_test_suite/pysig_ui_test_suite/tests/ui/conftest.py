"""Shared fixtures for PySig Studio browser tests."""

from __future__ import annotations

import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

import pytest
from playwright.sync_api import Page, expect


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_MODEL = Path(__file__).parent / "fixtures" / "ui_feature_test.yaml"
TEST_CONFIG_NAME = "ui_feature_test.yaml"


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_until_ready(url: str, process: subprocess.Popen, timeout_s: float = 15) -> None:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if process.poll() is not None:
            stdout = process.stdout.read() if process.stdout else ""
            raise RuntimeError(
                f"PySig Studio exited before becoming ready.\n{stdout}"
            )
        try:
            with urlopen(url, timeout=0.5) as response:
                if response.status == 200:
                    return
        except (URLError, TimeoutError, ConnectionError):
            time.sleep(0.1)
    process.terminate()
    raise TimeoutError(f"PySig Studio did not start within {timeout_s} seconds")


@pytest.fixture(scope="session")
def studio_project(tmp_path_factory) -> Path:
    """Create an isolated repository copy for destructive UI tests."""

    target = tmp_path_factory.mktemp("pysig-studio") / "repo"
    ignored = shutil.ignore_patterns(
        ".git",
        ".pytest_cache",
        "__pycache__",
        "*.pyc",
        "results",
        ".pysig_pdf",
        "test-results",
    )
    shutil.copytree(REPO_ROOT, target, ignore=ignored)
    (target / "configs").mkdir(exist_ok=True)
    shutil.copy2(FIXTURE_MODEL, target / "configs" / TEST_CONFIG_NAME)
    return target


@pytest.fixture(autouse=True)
def reset_ui_feature_model(studio_project):
    """Restore the deterministic YAML fixture before every UI test."""

    target = studio_project / "configs" / TEST_CONFIG_NAME
    shutil.copy2(FIXTURE_MODEL, target)
    yield


@pytest.fixture(scope="session")
def studio_server(studio_project):
    """Start one isolated PySig Studio server for the UI test session."""

    port = _free_port()
    url = f"http://127.0.0.1:{port}"
    command = [
        sys.executable,
        "pysig_ui.py",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
        "--no-browser",
    ]
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    process = subprocess.Popen(
        command,
        cwd=studio_project,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )
    _wait_until_ready(url, process)
    yield {"url": url, "process": process, "project": studio_project}
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()


@pytest.fixture
def studio_url(studio_server) -> str:
    return studio_server["url"]


@pytest.fixture
def browser_errors(page: Page):
    errors: list[str] = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.on(
        "console",
        lambda message: errors.append(message.text)
        if message.type == "error"
        else None,
    )
    return errors


@pytest.fixture
def studio_page(page: Page, studio_url: str, browser_errors):
    """Open Studio and fail if startup produces JavaScript errors."""

    page.goto(studio_url, wait_until="domcontentloaded")
    expect(page.locator("#app")).to_be_visible()
    expect(page.locator("#command-input")).to_be_editable()
    errors_at_start = list(browser_errors)
    assert errors_at_start == [], f"Browser startup errors: {errors_at_start}"
    return page


@pytest.fixture
def loaded_model(studio_page: Page):
    """Open the deterministic UI feature fixture through the interface."""

    page = studio_page
    page.get_by_text("Open", exact=True).first.click()
    expect(page.locator("#open-dialog")).to_be_visible()
    page.locator("#config-list").select_option(TEST_CONFIG_NAME)
    page.locator("#confirm-open").click()
    expect(page.locator("#open-dialog")).to_be_hidden()
    expect(page.locator('[data-type="lane"][data-id="A1_1"]')).to_be_visible()
    return page


@pytest.fixture
def model_api(studio_server):
    """Return a helper for retrieving current model JSON from Studio."""

    import json

    def fetch_model():
        with urlopen(studio_server["url"] + "/api/model") as response:
            return json.loads(response.read().decode("utf-8"))["model"]

    return fetch_model
