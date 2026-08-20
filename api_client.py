import os
from time import sleep
from typing import Any

import pytest
from playwright.sync_api import (
    APIRequestContext,
    APIResponse,
    Playwright,
)


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


def _get_json_with_retry(
    api_context: APIRequestContext,
    path: str,
) -> Any:
    response = None

    max_attempts = 8

    for attempt in range(max_attempts):
        response = api_context.get(path)
        if response.status == 200:
            return response.json()
        if response.status not in {500, 502, 503, 504}:
            break
        if attempt < max_attempts - 1:
            sleep(0.5)

    _assert_status(response, 200, "GET")


def reset_user(playwright: Playwright, launch_params: str) -> None:
    _validate_launch_params(launch_params)
    api_context = playwright.request.new_context(
        base_url=_get_api_url(),
        extra_http_headers={"X-VK-Launch-Params": launch_params},
    )

    try:
        response = None
        for attempt in range(5):
            response = api_context.post("v1/account/reset")
            if response.status == 200:
                break
            if response.status not in {502, 503, 504}:
                break
            if attempt < 4:
                sleep(0.25)
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


def get_user_inventory(
    playwright: Playwright,
    launch_params: str,
) -> list[dict[str, Any]]:
    _validate_launch_params(launch_params)
    api_context = playwright.request.new_context(
        base_url=_get_api_url(),
        extra_http_headers={"X-VK-Launch-Params": launch_params},
    )

    try:
        response = api_context.get("v1/inventory")
        _assert_status(response, 200, "GET")
        return response.json()
    finally:
        api_context.dispose()


def get_user_mail(
    playwright: Playwright,
    launch_params: str,
) -> dict[str, Any]:
    _validate_launch_params(launch_params)
    api_context = playwright.request.new_context(
        base_url=_get_api_url(),
        extra_http_headers={"X-VK-Launch-Params": launch_params},
    )

    try:
        response = api_context.get("mail?page=1&limit=100")
        _assert_status(response, 200, "GET")
        return response.json()
    finally:
        api_context.dispose()


def delete_user_mail(
    playwright: Playwright,
    launch_params: str,
    mail_id: str,
) -> None:
    _validate_launch_params(launch_params)
    api_context = playwright.request.new_context(
        base_url=_get_api_url(),
        extra_http_headers={"X-VK-Launch-Params": launch_params},
    )

    try:
        response = api_context.delete(f"mail/{mail_id}")
        _assert_status(response, 200, "DELETE")
    finally:
        api_context.dispose()


def get_user_guild(
    playwright: Playwright,
    launch_params: str,
) -> dict[str, Any] | list:
    _validate_launch_params(launch_params)
    api_context = playwright.request.new_context(
        base_url=_get_api_url(),
        extra_http_headers={"X-VK-Launch-Params": launch_params},
    )

    try:
        return _get_json_with_retry(api_context, "guild")
    finally:
        api_context.dispose()


def get_guild_members(
    playwright: Playwright,
    launch_params: str,
) -> list[dict[str, Any]]:
    _validate_launch_params(launch_params)
    api_context = playwright.request.new_context(
        base_url=_get_api_url(),
        extra_http_headers={"X-VK-Launch-Params": launch_params},
    )

    try:
        return _get_json_with_retry(api_context, "guild/members")
    finally:
        api_context.dispose()


def get_guild_applications(
    playwright: Playwright,
    launch_params: str,
) -> list[dict[str, Any]]:
    _validate_launch_params(launch_params)
    api_context = playwright.request.new_context(
        base_url=_get_api_url(),
        extra_http_headers={"X-VK-Launch-Params": launch_params},
    )

    try:
        return _get_json_with_retry(
            api_context,
            "guild/applications",
        )
    finally:
        api_context.dispose()


def kick_guild_member(
    playwright: Playwright,
    launch_params: str,
    unit_id: int,
) -> None:
    _validate_launch_params(launch_params)
    api_context = playwright.request.new_context(
        base_url=_get_api_url(),
        extra_http_headers={"X-VK-Launch-Params": launch_params},
    )

    try:
        response = api_context.post(
            "guild/kick",
            data={"unitId": unit_id},
        )
        _assert_status(response, 200, "POST")
    finally:
        api_context.dispose()


def leave_guild(
    playwright: Playwright,
    launch_params: str,
) -> None:
    _validate_launch_params(launch_params)
    api_context = playwright.request.new_context(
        base_url=_get_api_url(),
        extra_http_headers={"X-VK-Launch-Params": launch_params},
    )

    try:
        response = api_context.post("guild/leave")
        _assert_status(response, 200, "POST")
    finally:
        api_context.dispose()
