from urllib.parse import urlsplit

import pytest
from playwright.sync_api import Page, Playwright, Response, expect

from api_client import (
    get_required_env,
    get_user_inventory,
    unlock_inventory_item,
)


ITEM_ID = "eq_wep_t1"
ITEM_NAME = "Ржавый Меч"


def _is_post_response(response: Response, path: str) -> bool:
    return (
        response.request.method == "POST"
        and urlsplit(response.url).path == path
    )


def _get_item(playwright: Playwright, launch_params: str) -> dict:
    return next(
        item
        for item in get_user_inventory(playwright, launch_params)
        if item["id"] == ITEM_ID
    )


@pytest.mark.regression
def test_lock_item_blocks_dangerous_actions_and_unlock_restores_them(
    user_1_page: Page,
    playwright: Playwright,
) -> None:
    launch_params = get_required_env("VK_LAUNCH_PARAMS_USER_1")
    locked = False

    assert _get_item(playwright, launch_params)["isLocked"] is False

    try:
        user_1_page.goto(
            get_required_env("BASE_URL") + launch_params
        )
        user_1_page.get_by_role(
            "button",
            name="Сумка",
            exact=True,
        ).click()
        user_1_page.get_by_role(
            "button",
            name=ITEM_NAME,
            exact=True,
        ).click()

        item_dialog = user_1_page.get_by_role("dialog")
        with user_1_page.expect_response(
            lambda response: _is_post_response(
                response,
                "/api/inventory/lock",
            )
        ) as lock_response_info:
            item_dialog.get_by_role(
                "button",
                name="Заблокировать предмет",
            ).click()

        lock_response = lock_response_info.value

        assert lock_response.status == 200, (
            f"Item lock failed: {lock_response.text()}"
        )
        assert lock_response.request.post_data_json == {
            "itemId": ITEM_ID,
        }
        locked = True
        assert _get_item(playwright, launch_params)["isLocked"] is True

        blocked_actions = item_dialog.get_by_role(
            "button",
            name="Заблокировано",
            exact=True,
        )
        expect(blocked_actions).to_have_count(4)
        for index in range(4):
            expect(blocked_actions.nth(index)).to_be_disabled()

        for unavailable_action in (
            "Надеть",
            "На склад",
            "Разобрать",
        ):
            expect(
                item_dialog.get_by_role(
                    "button",
                    name=unavailable_action,
                    exact=True,
                )
            ).to_have_count(0)

        with user_1_page.expect_response(
            lambda response: _is_post_response(
                response,
                "/api/inventory/unlock",
            )
        ) as unlock_response_info:
            item_dialog.get_by_role(
                "button",
                name="Разблокировать предмет",
            ).click()

        unlock_response = unlock_response_info.value

        assert unlock_response.status == 200, (
            f"Item unlock failed: {unlock_response.text()}"
        )
        assert unlock_response.request.post_data_json == {
            "itemId": ITEM_ID,
        }
        locked = False
        assert _get_item(playwright, launch_params)["isLocked"] is False

        for restored_action in (
            "Надеть",
            "На склад",
            "Разобрать",
        ):
            expect(
                item_dialog.get_by_role(
                    "button",
                    name=restored_action,
                    exact=True,
                )
            ).to_be_enabled()
    finally:
        if locked:
            unlock_inventory_item(
                playwright,
                launch_params,
                ITEM_ID,
            )
