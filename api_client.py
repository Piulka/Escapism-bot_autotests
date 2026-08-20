import os
from typing import Any

import pytest
from playwright.sync_api import APIResponse, Playwright


def get_required_env(name: str) -> str:
    value = os.getenv(name)

    if not value:
        raise pytest.UsageError(
            f"Required environment variable {name} is not set. "
            "Copy .env.example to .env and fill in the values."
        )

    return value


def _get_api_url() -> str:
    api_url = get_required_env("API_URL")

    if not api_url.endswith("/"):
        raise pytest.UsageError(
            "API_URL must end with '/' because API endpoints are relative paths."
        )

    return api_url


def _validate_launch_params(launch_params: str) -> None:
    if not launch_params.startswith("?"):
        raise pytest.UsageError(
            "VK launch params must be a full query string starting with '?'."
        )


def _assert_status(
    response: APIResponse,
    expected_status: int,
    method: str,
) -> None:
    assert response.status == expected_status, (
        f"Unexpected response from {method} {response.url}. "
        f"Expected status: {expected_status}, actual status: {response.status}. "
        f"Body: {response.text()}"
    )


def reset_user(playwright: Playwright, launch_params: str) -> None:
    _validate_launch_params(launch_params)
    api_context = playwright.request.new_context(
        base_url=_get_api_url(),
        extra_http_headers={"X-VK-Launch-Params": launch_params},
    )

    try:
        response = api_context.post("v1/account/reset")
        _assert_status(response, 200, "POST")
    finally:
        api_context.dispose()


def get_user_profile(
    playwright: Playwright,
    launch_params: str,
) -> dict[str, Any]:
    _validate_launch_params(launch_params)
    api_context = playwright.request.new_context(
        base_url=_get_api_url(),
        extra_http_headers={"X-VK-Launch-Params": launch_params},
    )

    try:
        response = api_context.get("v1/profile")
        _assert_status(response, 200, "GET")
        return response.json()
    finally:
        api_context.dispose()


def get_exchange_pool(
    playwright: Playwright,
    launch_params: str,
) -> dict[str, int]:
    _validate_launch_params(launch_params)
    api_context = playwright.request.new_context(
        base_url=_get_api_url(),
        extra_http_headers={"X-VK-Launch-Params": launch_params},
    )

    try:
        response = api_context.get("exchange/pool")
        _assert_status(response, 200, "GET")
        return response.json()
    finally:
        api_context.dispose()
