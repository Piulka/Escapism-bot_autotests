import re
from urllib.parse import urlsplit

import pytest
from playwright.sync_api import Locator, Page, Playwright, Response, expect

from api_client import (
    get_required_env,
    get_user_inventory,
    get_user_profile,
    get_user_warehouse,
    reset_user,
    unequip_inventory_item,
    unlock_inventory_item,
    withdraw_warehouse_item,
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


def _has_item(items: list[dict], item_id: str) -> bool:
    return any(item["id"] == item_id for item in items)


def _get_main_hand_slot(page: Page) -> Locator:
    return page.get_by_test_id("equipment-slot-mainHand")


@pytest.mark.regression
def test_equip_item_through_equipment_slot(
    user_1_page: Page,
    playwright: Playwright,
) -> None:
    launch_params = get_required_env("VK_LAUNCH_PARAMS_USER_1")
    equipped = False

    try:
        user_1_page.goto(
            get_required_env("BASE_URL") + launch_params
        )
        user_1_page.get_by_role(
            "button",
            name="Сумка",
            exact=True,
        ).click()

        _get_main_hand_slot(user_1_page).click()
        item_picker = user_1_page.get_by_role(
            "dialog",
            name="Выбор: Правая рука",
        )

        with user_1_page.expect_response(
            lambda response: _is_post_response(
                response,
                "/api/inventory/equip",
            )
        ) as equip_response_info:
            item_picker.get_by_role(
                "button",
                name=ITEM_NAME,
                exact=True,
            ).click()

        equip_response = equip_response_info.value

        assert equip_response.status == 200, (
            f"Item equip failed: {equip_response.text()}"
        )
        assert equip_response.request.post_data_json == {
            "itemId": ITEM_ID,
            "slotKey": "mainHand",
        }
        equipped = True

        profile = get_user_profile(playwright, launch_params)
        assert profile["equipment"]["mainHand"]["id"] == ITEM_ID
    finally:
        if equipped:
            unequip_inventory_item(
                playwright,
                launch_params,
                "mainHand",
            )


@pytest.mark.regression
def test_move_item_between_inventory_warehouse_and_equipment(
    user_1_page: Page,
    playwright: Playwright,
) -> None:
    launch_params = get_required_env("VK_LAUNCH_PARAMS_USER_1")
    item_location = "inventory"

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

        with user_1_page.expect_response(
            lambda response: _is_post_response(
                response,
                "/api/warehouse/deposit",
            )
        ) as deposit_response_info:
            user_1_page.get_by_role(
                "button",
                name="На склад",
                exact=True,
            ).click()

        deposit_response = deposit_response_info.value
        item_location = "warehouse"
        assert deposit_response.status == 200, (
            f"Warehouse deposit failed: {deposit_response.text()}"
        )
        assert deposit_response.request.post_data_json == {
            "itemId": ITEM_ID,
            "quantity": 1,
        }
        assert not _has_item(
            get_user_inventory(playwright, launch_params),
            ITEM_ID,
        )
        assert _has_item(
            get_user_warehouse(playwright, launch_params),
            ITEM_ID,
        )

        user_1_page.keyboard.press("Escape")
        user_1_page.get_by_role(
            "button",
            name=re.compile(r"^Склад"),
        ).click()
        user_1_page.get_by_role(
            "button",
            name=ITEM_NAME,
            exact=True,
        ).click()

        with user_1_page.expect_response(
            lambda response: _is_post_response(
                response,
                "/api/inventory/equip",
            )
        ) as equip_response_info:
            user_1_page.get_by_role(
                "button",
                name="Надеть",
                exact=True,
            ).click()

        equip_response = equip_response_info.value
        item_location = "equipment"
        assert equip_response.status == 200, (
            f"Equip from warehouse failed: {equip_response.text()}"
        )
        assert equip_response.request.post_data_json == {
            "itemId": ITEM_ID,
            "slotKey": "mainHand",
        }
        assert not _has_item(
            get_user_warehouse(playwright, launch_params),
            ITEM_ID,
        )
        assert (
            get_user_profile(playwright, launch_params)["equipment"]
            ["mainHand"]["id"]
            == ITEM_ID
        )

        _get_main_hand_slot(user_1_page).click()
        with user_1_page.expect_response(
            lambda response: _is_post_response(
                response,
                "/api/warehouse/deposit",
            )
        ) as equipped_deposit_response_info:
            user_1_page.get_by_role(
                "button",
                name="На склад",
                exact=True,
            ).click()

        equipped_deposit_response = equipped_deposit_response_info.value
        item_location = "warehouse"
        assert equipped_deposit_response.status == 200, (
            "Equipped item deposit failed: "
            f"{equipped_deposit_response.text()}"
        )
        assert equipped_deposit_response.request.post_data_json == {
            "itemId": ITEM_ID,
            "quantity": 1,
        }
        assert (
            get_user_profile(playwright, launch_params)["equipment"]
            ["mainHand"]
            is None
        )
        assert _has_item(
            get_user_warehouse(playwright, launch_params),
            ITEM_ID,
        )

        # Remount the warehouse list after the cross-state mutation without
        # reloading the whole app and its bootstrap data.
        user_1_page.get_by_role(
            "button",
            name="Сумка",
            exact=False,
        ).first.click()
        user_1_page.get_by_role(
            "button",
            name=re.compile(r"^Склад"),
        ).click()
        warehouse_item = user_1_page.get_by_role(
            "button",
            name=ITEM_NAME,
            exact=True,
        )
        expect(warehouse_item).to_be_visible()
        warehouse_item.click()
        with user_1_page.expect_response(
            lambda response: _is_post_response(
                response,
                "/api/warehouse/withdraw",
            )
        ) as withdraw_response_info:
            user_1_page.get_by_role(
                "button",
                name="В сумку",
                exact=True,
            ).click()

        withdraw_response = withdraw_response_info.value
        item_location = "inventory"
        assert withdraw_response.status == 200, (
            f"Warehouse withdrawal failed: {withdraw_response.text()}"
        )
        assert withdraw_response.request.post_data_json == {
            "itemId": ITEM_ID,
            "quantity": 1,
        }
        assert _has_item(
            get_user_inventory(playwright, launch_params),
            ITEM_ID,
        )
        assert not _has_item(
            get_user_warehouse(playwright, launch_params),
            ITEM_ID,
        )
    finally:
        if item_location == "equipment":
            unequip_inventory_item(
                playwright,
                launch_params,
                "mainHand",
            )
        elif item_location == "warehouse":
            withdraw_warehouse_item(
                playwright,
                launch_params,
                ITEM_ID,
                1,
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

        for blocked_action in (
            "Надеть — заблокировано",
            "На склад — заблокировано",
            "Разобрать — заблокировано",
            "Выбросить предмет",
        ):
            expect(
                item_dialog.get_by_role(
                    "button",
                    name=blocked_action,
                    exact=True,
                )
            ).to_be_disabled()

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


@pytest.mark.regression
def test_trash_item_requires_confirmation_and_removes_it(
    user_1_page: Page,
    playwright: Playwright,
) -> None:
    launch_params = get_required_env("VK_LAUNCH_PARAMS_USER_1")

    assert _has_item(
        get_user_inventory(playwright, launch_params),
        ITEM_ID,
    )

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

        user_1_page.get_by_role(
            "button",
            name="Выбросить предмет",
            exact=True,
        ).click()

        confirmation = user_1_page.get_by_role(
            "dialog",
            name=re.compile(r"Выбросить"),
        )
        expect(confirmation).to_be_visible()
        expect(confirmation).to_contain_text(ITEM_NAME)

        with user_1_page.expect_response(
            lambda response: _is_post_response(
                response,
                "/api/inventory/trash",
            )
        ) as trash_response_info:
            confirmation.get_by_role(
                "button",
                name="Выбросить",
                exact=True,
            ).click()

        trash_response = trash_response_info.value
        assert trash_response.status == 200, (
            f"Item trash failed: {trash_response.text()}"
        )
        assert trash_response.request.post_data_json == {
            "itemId": ITEM_ID,
        }
        assert not _has_item(
            get_user_inventory(playwright, launch_params),
            ITEM_ID,
        )
        expect(
            user_1_page.get_by_role(
                "button",
                name=ITEM_NAME,
                exact=True,
            )
        ).to_have_count(0)
    finally:
        reset_user(playwright, launch_params)
