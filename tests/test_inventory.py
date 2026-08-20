import os

import pytest
from playwright.sync_api import Playwright

from conftest import get_user_profile


@pytest.mark.smoke
def test_equip_and_unequip_item(
    user_1_page,
    playwright: Playwright
):
    base_url = os.getenv("BASE_URL")
    launch_params = os.getenv("VK_LAUNCH_PARAMS_USER_1")

    user_1_page.goto(f"{base_url}{launch_params}")

    user_1_page.get_by_role(
        "button",
        name="Инвентарь"
    ).click()

    item = user_1_page.get_by_role(
        "button",
        name="Шлем Ополченца"
    )

    item.click()

    with user_1_page.expect_response(
        lambda response: "/api/inventory/equip" in response.url
    ) as equip_response_info:
        user_1_page.get_by_role(
            "button",
            name="Надеть"
        ).click()

    equip_response = equip_response_info.value

    assert equip_response.status == 200

    profile = get_user_profile(
        playwright,
        launch_params
    )

    assert profile["equipment"]["head"]["id"] == "eq_head_t1"

    user_1_page.locator("svg").nth(3).click()

    with user_1_page.expect_response(
        lambda response: "/api/inventory/unequip" in response.url
    ) as unequip_response_info:
        user_1_page.get_by_role(
            "button",
            name="Снять"
        ).click()

    unequip_response = unequip_response_info.value

    assert unequip_response.status == 200

    profile = get_user_profile(
        playwright,
        launch_params
    )

    assert profile["equipment"]["head"] is None