from urllib.parse import urlsplit

import pytest
from playwright.sync_api import Page, Playwright, Response

from api_client import get_required_env, get_user_profile


def _is_post_response(response: Response, path: str) -> bool:
    return (
        response.request.method == "POST"
        and urlsplit(response.url).path == path
    )


@pytest.mark.smoke
def test_equip_and_unequip_item(
    user_1_page: Page,
    playwright: Playwright,
) -> None:
    base_url = get_required_env("BASE_URL")
    launch_params = get_required_env("VK_LAUNCH_PARAMS_USER_1")

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
        lambda response: _is_post_response(
            response,
            "/api/inventory/equip",
        )
    ) as equip_response_info:
        user_1_page.get_by_role(
            "button",
            name="Надеть"
        ).click()

    equip_response = equip_response_info.value

    assert equip_response.status == 200, (
        f"Equip request failed: {equip_response.text()}"
    )

    profile = get_user_profile(
        playwright,
        launch_params
    )

    assert profile["equipment"]["head"]["id"] == "eq_head_t1"

    # TODO: replace with a data-testid/aria-label when the head slot gets one.
    user_1_page.locator("svg").nth(3).click()

    with user_1_page.expect_response(
        lambda response: _is_post_response(
            response,
            "/api/inventory/unequip",
        )
    ) as unequip_response_info:
        user_1_page.get_by_role(
            "button",
            name="Снять"
        ).click()

    unequip_response = unequip_response_info.value

    assert unequip_response.status == 200, (
        f"Unequip request failed: {unequip_response.text()}"
    )

    profile = get_user_profile(
        playwright,
        launch_params
    )

    assert profile["equipment"]["head"] is None
