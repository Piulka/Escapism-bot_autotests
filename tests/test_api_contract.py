import re

import pytest
from playwright.sync_api import Page, Playwright, expect

from api_client import (
    get_backend_timing_headers,
    get_required_env,
    get_user_bootstrap,
)


@pytest.mark.regression
def test_bootstrap_returns_profile_and_lightweight_counters(
    reset_user_1: None,
    playwright: Playwright,
) -> None:
    launch_params = get_required_env("VK_LAUNCH_PARAMS_USER_1")
    bootstrap = get_user_bootstrap(playwright, launch_params)

    assert "profile" in bootstrap
    assert "inventory" not in bootstrap
    assert bootstrap["inventoryCount"] == 9
    assert bootstrap["unreadMailsCount"] == 3
    assert bootstrap["pendingGuildApplicationsCount"] == 0


@pytest.mark.regression
def test_api_exposes_backend_processing_time_headers(
    reset_user_1: None,
    playwright: Playwright,
) -> None:
    launch_params = get_required_env("VK_LAUNCH_PARAMS_USER_1")
    headers = get_backend_timing_headers(playwright, launch_params)

    assert re.fullmatch(
        r"app;dur=\d+(?:\.\d+)?",
        headers["server-timing"],
    )
    assert float(headers["x-response-time"]) >= 0


@pytest.mark.regression
def test_header_refresh_requests_fresh_profile(
    user_1_page: Page,
) -> None:
    launch_params = get_required_env("VK_LAUNCH_PARAMS_USER_1")
    user_1_page.goto(get_required_env("BASE_URL") + launch_params)
    refresh_button = user_1_page.get_by_role(
        "button",
        name="Обновить данные",
        exact=True,
    )
    expect(refresh_button).to_be_visible()

    responses: list[tuple[str, int]] = []
    user_1_page.on(
        "response",
        lambda response: responses.append((response.url, response.status))
        if response.request.method == "GET"
        else None,
    )
    refresh_button.click()
    user_1_page.wait_for_timeout(1_000)

    assert responses, "Refresh button did not initiate any GET request"
    assert any(
        url.endswith("/api/v1/profile") and status == 200
        for url, status in responses
    ), responses
