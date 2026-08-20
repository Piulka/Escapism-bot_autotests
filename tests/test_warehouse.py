import re
from urllib.parse import urlsplit

import pytest
from playwright.sync_api import Page, Playwright, Response

from api_client import (
    get_required_env,
    get_user_inventory,
    get_user_warehouse,
    withdraw_warehouse_item,
)


ITEM_ID = "food_raw_1"
ITEM_NAME = "Морковь"
TRANSFER_QUANTITY = 3


def _is_post_response(response: Response, path: str) -> bool:
    return (
        response.request.method == "POST"
        and urlsplit(response.url).path == path
    )


def _item_quantity(items: list[dict], item_id: str) -> int:
    return next(
        (
            item["quantity"]
            for item in items
            if item["id"] == item_id
        ),
        0,
    )


@pytest.mark.smoke
def test_deposit_item_to_warehouse_and_withdraw_it(
    user_1_page: Page,
    playwright: Playwright,
) -> None:
    launch_params = get_required_env("VK_LAUNCH_PARAMS_USER_1")
    inventory_before = get_user_inventory(playwright, launch_params)
    warehouse_before = get_user_warehouse(playwright, launch_params)
    inventory_quantity_before = _item_quantity(
        inventory_before,
        ITEM_ID,
    )
    warehouse_quantity_before = _item_quantity(
        warehouse_before,
        ITEM_ID,
    )
    deposited = False

    assert inventory_quantity_before >= TRANSFER_QUANTITY

    try:
        user_1_page.goto(
            get_required_env("BASE_URL") + launch_params
        )
        user_1_page.get_by_role(
            "button",
            name="Сумка",
            exact=True,
        ).click()
        user_1_page.get_by_label(ITEM_NAME, exact=True).click()

        user_1_page.get_by_role(
            "button",
            name="На склад",
        ).click()
        user_1_page.get_by_label("Количество").fill(
            str(TRANSFER_QUANTITY)
        )

        with user_1_page.expect_response(
            lambda response: _is_post_response(
                response,
                "/api/warehouse/deposit",
            )
        ) as deposit_response_info:
            user_1_page.get_by_role(
                "button",
                name="Положить на склад",
            ).click()

        deposit_response = deposit_response_info.value

        assert deposit_response.status == 200, (
            f"Warehouse deposit failed: {deposit_response.text()}"
        )
        assert deposit_response.request.post_data_json == {
            "itemId": ITEM_ID,
            "quantity": TRANSFER_QUANTITY,
        }
        deposited = True

        inventory_after_deposit = get_user_inventory(
            playwright,
            launch_params,
        )
        warehouse_after_deposit = get_user_warehouse(
            playwright,
            launch_params,
        )

        assert _item_quantity(
            inventory_after_deposit,
            ITEM_ID,
        ) == inventory_quantity_before - TRANSFER_QUANTITY
        assert _item_quantity(
            warehouse_after_deposit,
            ITEM_ID,
        ) == warehouse_quantity_before + TRANSFER_QUANTITY

        user_1_page.keyboard.press("Escape")
        user_1_page.get_by_role(
            "button",
            name=re.compile(r"^Склад"),
        ).click()
        user_1_page.get_by_label(ITEM_NAME, exact=True).click()

        user_1_page.get_by_role(
            "button",
            name="В сумку",
        ).click()
        user_1_page.get_by_label("Количество").fill(
            str(TRANSFER_QUANTITY)
        )

        with user_1_page.expect_response(
            lambda response: _is_post_response(
                response,
                "/api/warehouse/withdraw",
            )
        ) as withdraw_response_info:
            user_1_page.get_by_role(
                "button",
                name="Забрать в сумку",
            ).click()

        withdraw_response = withdraw_response_info.value

        assert withdraw_response.status == 200, (
            f"Warehouse withdrawal failed: {withdraw_response.text()}"
        )
        assert withdraw_response.request.post_data_json == {
            "itemId": ITEM_ID,
            "quantity": TRANSFER_QUANTITY,
        }
        deposited = False

        inventory_after_withdraw = get_user_inventory(
            playwright,
            launch_params,
        )
        warehouse_after_withdraw = get_user_warehouse(
            playwright,
            launch_params,
        )

        assert _item_quantity(
            inventory_after_withdraw,
            ITEM_ID,
        ) == inventory_quantity_before
        assert _item_quantity(
            warehouse_after_withdraw,
            ITEM_ID,
        ) == warehouse_quantity_before
    finally:
        if deposited:
            withdraw_warehouse_item(
                playwright,
                launch_params,
                ITEM_ID,
                TRANSFER_QUANTITY,
            )
