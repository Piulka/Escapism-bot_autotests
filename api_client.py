import os
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


def _get_json(
    api_context: APIRequestContext,
    path: str,
) -> Any:
    response = api_context.get(path)
    _assert_status(response, 200, "GET")
    return response.json()


def reset_user(
    playwright: Playwright,
    launch_params: str,
) -> dict[str, Any]:
    _validate_launch_params(launch_params)
    api_context = playwright.request.new_context(
        base_url=_get_api_url(),
        extra_http_headers={"X-VK-Launch-Params": launch_params},
    )

    try:
        response = api_context.post("v1/account/reset")
        _assert_status(response, 200, "POST")
        return response.json()
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
        return _get_json(api_context, "v1/profile")
    finally:
        api_context.dispose()


def inject_skill_experience(
    playwright: Playwright,
    launch_params: str,
    skill_id: str,
    amount: int,
    *,
    use_lp: bool,
) -> None:
    _validate_launch_params(launch_params)
    assert 1 <= amount <= 100_000
    api_context = playwright.request.new_context(
        base_url=_get_api_url(),
        extra_http_headers={"X-VK-Launch-Params": launch_params},
    )

    try:
        response = api_context.post(
            "skills/inject",
            data={
                "skillId": skill_id,
                "amount": amount,
                "useLp": use_lp,
            },
        )
        _assert_status(response, 200, "POST")
    finally:
        api_context.dispose()


def get_user_titles(
    playwright: Playwright,
    launch_params: str,
) -> list[dict[str, Any]]:
    _validate_launch_params(launch_params)
    api_context = playwright.request.new_context(
        base_url=_get_api_url(),
        extra_http_headers={"X-VK-Launch-Params": launch_params},
    )

    try:
        return _get_json(api_context, "v1/titles")
    finally:
        api_context.dispose()


def select_user_title(
    playwright: Playwright,
    launch_params: str,
    title_id: int,
) -> None:
    _validate_launch_params(launch_params)
    api_context = playwright.request.new_context(
        base_url=_get_api_url(),
        extra_http_headers={"X-VK-Launch-Params": launch_params},
    )

    try:
        response = api_context.post(
            "v1/titles/select",
            data={"titleId": title_id},
        )
        _assert_status(response, 200, "POST")
    finally:
        api_context.dispose()


def select_profile_customization(
    playwright: Playwright,
    launch_params: str,
    endpoint: str,
    payload_key: str,
    value: int,
) -> None:
    _validate_launch_params(launch_params)
    assert endpoint in {"banner", "frame", "avatar"}
    assert payload_key == f"{endpoint}Id"
    api_context = playwright.request.new_context(
        base_url=_get_api_url(),
        extra_http_headers={"X-VK-Launch-Params": launch_params},
    )

    try:
        response = api_context.post(
            f"v1/profile/{endpoint}",
            data={payload_key: value},
        )
        _assert_status(response, 200, "POST")
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
        return _get_json(api_context, "exchange/pool")
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
        return _get_json(api_context, "v1/inventory")
    finally:
        api_context.dispose()


def get_user_warehouse(
    playwright: Playwright,
    launch_params: str,
) -> list[dict[str, Any]]:
    _validate_launch_params(launch_params)
    api_context = playwright.request.new_context(
        base_url=_get_api_url(),
        extra_http_headers={"X-VK-Launch-Params": launch_params},
    )

    try:
        return _get_json(api_context, "warehouse")
    finally:
        api_context.dispose()


def withdraw_warehouse_item(
    playwright: Playwright,
    launch_params: str,
    item_id: str,
    quantity: int,
) -> None:
    _validate_launch_params(launch_params)
    api_context = playwright.request.new_context(
        base_url=_get_api_url(),
        extra_http_headers={"X-VK-Launch-Params": launch_params},
    )

    try:
        response = api_context.post(
            "warehouse/withdraw",
            data={"itemId": item_id, "quantity": quantity},
        )
        _assert_status(response, 200, "POST")
    finally:
        api_context.dispose()


def unlock_inventory_item(
    playwright: Playwright,
    launch_params: str,
    item_id: str,
) -> None:
    _validate_launch_params(launch_params)
    api_context = playwright.request.new_context(
        base_url=_get_api_url(),
        extra_http_headers={"X-VK-Launch-Params": launch_params},
    )

    try:
        response = api_context.post(
            "inventory/unlock",
            data={"itemId": item_id},
        )
        _assert_status(response, 200, "POST")
    finally:
        api_context.dispose()


def unequip_inventory_item(
    playwright: Playwright,
    launch_params: str,
    slot_key: str,
) -> None:
    _validate_launch_params(launch_params)
    api_context = playwright.request.new_context(
        base_url=_get_api_url(),
        extra_http_headers={"X-VK-Launch-Params": launch_params},
    )

    try:
        response = api_context.post(
            "inventory/unequip",
            data={"slotKey": slot_key},
        )
        _assert_status(response, 200, "POST")
    finally:
        api_context.dispose()


def equip_inventory_item(
    playwright: Playwright,
    launch_params: str,
    item_id: str,
    slot_key: str,
) -> None:
    _validate_launch_params(launch_params)
    api_context = playwright.request.new_context(
        base_url=_get_api_url(),
        extra_http_headers={"X-VK-Launch-Params": launch_params},
    )

    try:
        response = api_context.post(
            "inventory/equip",
            data={"itemId": item_id, "slotKey": slot_key},
        )
        _assert_status(response, 200, "POST")
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
        return _get_json(
            api_context,
            "mail?page=1&limit=100",
        )
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


def send_user_mail(
    playwright: Playwright,
    launch_params: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    _validate_launch_params(launch_params)
    api_context = playwright.request.new_context(
        base_url=_get_api_url(),
        extra_http_headers={"X-VK-Launch-Params": launch_params},
    )

    try:
        response = api_context.post("mail/send", data=payload)
        _assert_status(response, 200, "POST")
        return response.json()
    finally:
        api_context.dispose()


def claim_user_mail(
    playwright: Playwright,
    launch_params: str,
    mail_id: str,
) -> dict[str, Any]:
    _validate_launch_params(launch_params)
    api_context = playwright.request.new_context(
        base_url=_get_api_url(),
        extra_http_headers={"X-VK-Launch-Params": launch_params},
    )

    try:
        response = api_context.post(
            "mail/claim",
            data={"mailId": mail_id},
        )
        _assert_status(response, 200, "POST")
        return response.json()
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
        return _get_json(api_context, "guild")
    finally:
        api_context.dispose()


def create_user_guild(
    playwright: Playwright,
    launch_params: str,
    name: str,
    tag: str,
) -> None:
    _validate_launch_params(launch_params)
    api_context = playwright.request.new_context(
        base_url=_get_api_url(),
        extra_http_headers={"X-VK-Launch-Params": launch_params},
    )

    try:
        response = api_context.post(
            "guild/create",
            data={"name": name, "tag": tag},
        )
        _assert_status(response, 200, "POST")
    finally:
        api_context.dispose()


def apply_to_guild(
    playwright: Playwright,
    launch_params: str,
    guild_id: int,
) -> None:
    _validate_launch_params(launch_params)
    api_context = playwright.request.new_context(
        base_url=_get_api_url(),
        extra_http_headers={"X-VK-Launch-Params": launch_params},
    )

    try:
        response = api_context.post(
            "guild/join",
            data={"guildId": guild_id},
        )
        _assert_status(response, 200, "POST")
    finally:
        api_context.dispose()


def decide_guild_application(
    playwright: Playwright,
    launch_params: str,
    application_id: int,
    decision: str,
) -> None:
    _validate_launch_params(launch_params)
    api_context = playwright.request.new_context(
        base_url=_get_api_url(),
        extra_http_headers={"X-VK-Launch-Params": launch_params},
    )

    try:
        response = api_context.post(
            f"guild/applications/{application_id}/{decision}"
        )
        _assert_status(response, 200, "POST")
    finally:
        api_context.dispose()


def attempt_kick_guild_member(
    playwright: Playwright,
    launch_params: str,
    unit_id: int,
) -> tuple[int, dict[str, Any]]:
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
        return response.status, response.json()
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
        return _get_json(api_context, "guild/members")
    finally:
        api_context.dispose()


def get_guild_technologies(
    playwright: Playwright,
    launch_params: str,
) -> list[dict[str, Any]]:
    _validate_launch_params(launch_params)
    api_context = playwright.request.new_context(
        base_url=_get_api_url(),
        extra_http_headers={"X-VK-Launch-Params": launch_params},
    )

    try:
        return _get_json(api_context, "guild/techs")
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
        return _get_json(
            api_context,
            "guild/applications",
        )
    finally:
        api_context.dispose()


def attempt_guild_technology_action(
    playwright: Playwright,
    launch_params: str,
    action: str,
    technology_id: str,
) -> tuple[int, dict[str, Any]]:
    _validate_launch_params(launch_params)
    assert action in {"activate", "deactivate"}
    api_context = playwright.request.new_context(
        base_url=_get_api_url(),
        extra_http_headers={"X-VK-Launch-Params": launch_params},
    )

    try:
        response = api_context.post(
            f"guild/techs/{action}",
            data={"techId": technology_id},
        )
        return response.status, response.json()
    finally:
        api_context.dispose()


def invest_in_guild_technology(
    playwright: Playwright,
    launch_params: str,
    technology_id: str,
    amount: int,
) -> None:
    _validate_launch_params(launch_params)
    assert amount > 0
    api_context = playwright.request.new_context(
        base_url=_get_api_url(),
        extra_http_headers={"X-VK-Launch-Params": launch_params},
    )

    try:
        response = api_context.post(
            "guild/techs/invest",
            data={"techId": technology_id, "amount": amount},
        )
        _assert_status(response, 200, "POST")
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
