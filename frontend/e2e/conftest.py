import os
import re
from pathlib import Path

import pytest
from playwright.sync_api import Browser, Page, sync_playwright


ARTIFACTS = Path(__file__).resolve().parents[1] / "e2e-artifacts"


def pytest_configure():
    ARTIFACTS.mkdir(parents=True, exist_ok=True)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    setattr(item, f"rep_{call.when}", outcome.get_result())


@pytest.fixture(scope="session")
def browser() -> Browser:
    with sync_playwright() as playwright:
        browser_path = os.environ.get("E2E_BROWSER_PATH")
        if browser_path:
            browser = playwright.chromium.launch(
                headless=True, executable_path=browser_path
            )
        else:
            browser = playwright.chromium.launch(headless=True)
        yield browser
        browser.close()


@pytest.fixture
def app_base_url() -> str:
    return os.environ.get("E2E_BASE_URL", "http://127.0.0.1:5173")


@pytest.fixture
def api_base_url() -> str:
    return os.environ.get("E2E_API_BASE_URL", "http://127.0.0.1:8000/api/v1")


@pytest.fixture
def page(browser: Browser, request: pytest.FixtureRequest, app_base_url: str) -> Page:
    context = browser.new_context(viewport={"width": 1440, "height": 1000})
    context.tracing.start(screenshots=True, snapshots=True, sources=True)
    page = context.new_page()
    page.set_default_timeout(10_000)
    page.goto(app_base_url)
    yield page

    report = getattr(request.node, "rep_call", None)
    if report is None or not report.failed:
        report = getattr(request.node, "rep_setup", None)
    if report and report.failed:
        filename = re.sub(r"[^A-Za-z0-9_.-]+", "-", request.node.nodeid)
        page.screenshot(path=str(ARTIFACTS / f"{filename}.png"), full_page=True)
        context.tracing.stop(path=str(ARTIFACTS / f"{filename}-trace.zip"))
    else:
        context.tracing.stop()
    context.close()


@pytest.fixture
def demo_password() -> str:
    password = os.environ.get("E2E_DEMO_PASSWORD")
    if not password:
        pytest.fail("Set E2E_DEMO_PASSWORD to the password used by seed_demo.py")
    return password
