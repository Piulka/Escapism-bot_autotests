from urllib.parse import urlsplit

import pytest
from playwright.sync_api import Page, Playwright, Response

from api_client import (
    get_required_env,
    get_user_inventory,
    get_user_profile,
    reset_user,
)


ITEM_ID = "food_raw_1"
ITEM_NAME = "Морковь"


def _is_eat_response(response: Response) -> bool:
    return (
        response.request.method == "POST"
        and urlsplit(response.url).path == "/api/inventory/eat"
    )


def _get_item(inventory: list[dict], item_id: str) -> dict:
    return next(item for item in inventory if item["id"] == item_id)


@pytest.mark.smoke
def test_eat_food_and_increase_fullness(
    user_1_page: Page,
    playwright: Playwright,
) -> None:
    launch_params = get_required_env("VK_LAUNCH_PARAMS_USER_1")
    profile_before = get_user_profile(playwright, launch_params)
    inventory_before = get_user_inventory(playwright, launch_params)
    item_before = _get_item(inventory_before, ITEM_ID)
    stomach_before = profile_before["stomach"]

    assert item_before["quantity"] >= 1
    assert item_before["calories"] > 0
    assert (
        stomach_before["fullness"] + item_before["calories"]
        <= stomach_before["maxFullness"]
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
        user_1_page.get_by_label(ITEM_NAME, exact=True).click()

        with user_1_page.expect_response(
            _is_eat_response,
        ) as eat_response_info:
            user_1_page.get_by_role(
                "button",
                name="Съесть",
            ).click()

        eat_response = eat_response_info.value

        assert eat_response.status == 200, (
            f"Eating food failed: {eat_response.text()}"
        )
        assert eat_response.request.post_data_json == {
            "itemId": ITEM_ID,
        }

        profile_after = get_user_profile(playwright, launch_params)
        inventory_after = get_user_inventory(playwright, launch_params)
        item_after = _get_item(inventory_after, ITEM_ID)

        assert item_after["quantity"] == item_before["quantity"] - 1
        assert profile_after["stomach"]["fullness"] == (
            stomach_before["fullness"] + item_before["calories"]
        )
        assert profile_after["stomach"]["maxFullness"] == (
            stomach_before["maxFullness"]
        )
    finally:
        reset_user(playwright, launch_params)
