import re
from urllib.parse import urlsplit

import pytest
from playwright.sync_api import Page, Playwright, Response, expect

from api_client import (
    get_required_env,
    get_user_profile,
    get_user_titles,
    select_profile_customization,
    select_user_title,
)


def _is_title_select_response(response: Response) -> bool:
    return (
        response.request.method == "POST"
        and urlsplit(response.url).path == "/api/v1/titles/select"
    )


def _is_customization_response(response: Response, endpoint: str) -> bool:
    return (
        response.request.method == "POST"
        and urlsplit(response.url).path == f"/api/v1/profile/{endpoint}"
    )


@pytest.mark.regression
def test_select_profile_title_through_card_settings(
    user_1_page: Page,
    playwright: Playwright,
) -> None:
    launch_params = get_required_env("VK_LAUNCH_PARAMS_USER_1")
    profile_before = get_user_profile(playwright, launch_params)
    titles = get_user_titles(playwright, launch_params)
    target_title = next(
        title
        for title in titles
        if title["id"] != profile_before["titleId"]
    )

    try:
        user_1_page.goto(get_required_env("BASE_URL") + launch_params)
        # UI-019: the icon button currently exposes only an HTML title.
        user_1_page.get_by_title("Настройка карточки").click()
        settings_dialog = user_1_page.get_by_role("dialog").filter(
            has=user_1_page.get_by_role("button", name="Титул", exact=True)
        )
        expect(settings_dialog).to_be_visible()
        settings_dialog.get_by_role(
            "button",
            name="Титул",
            exact=True,
        ).click()

        with user_1_page.expect_response(
            _is_title_select_response,
        ) as select_response_info:
            settings_dialog.get_by_role(
                "button",
                name=target_title["name"],
                exact=True,
            ).click()

        select_response = select_response_info.value
        assert select_response.status == 200, select_response.text()
        assert select_response.request.post_data_json == {
            "titleId": target_title["id"]
        }
        profile_after = get_user_profile(playwright, launch_params)
        assert profile_after["titleId"] == target_title["id"]
        assert profile_after["title"] == target_title["name"]
        expect(
            user_1_page.locator("main").get_by_text(
                target_title["name"],
                exact=True,
            )
        ).to_be_visible()
    finally:
        select_user_title(
            playwright,
            launch_params,
            profile_before["titleId"],
        )


@pytest.mark.regression
@pytest.mark.parametrize(
    (
        "tab_name",
        "endpoint",
        "profile_field",
        "primary",
        "primary_id",
        "fallback",
        "fallback_id",
    ),
    [
        pytest.param(
            "Фон",
            "banner",
            "bannerId",
            "Ночное небо",
            1,
            "Вулкан",
            0,
            id="banner",
        ),
        pytest.param(
            "Рамка",
            "frame",
            "frameId",
            "Серебро",
            1,
            "Без рамки",
            0,
            id="frame",
        ),
        pytest.param(
            "Аватар",
            "avatar",
            "avatarId",
            "Череп",
            1,
            "Рыцарь",
            0,
            id="avatar",
        ),
    ],
)
def test_select_profile_visual_customization(
    user_1_page: Page,
    playwright: Playwright,
    tab_name: str,
    endpoint: str,
    profile_field: str,
    primary: str,
    primary_id: int,
    fallback: str,
    fallback_id: int,
) -> None:
    launch_params = get_required_env("VK_LAUNCH_PARAMS_USER_1")
    profile_before = get_user_profile(playwright, launch_params)
    original_id = profile_before[profile_field]

    try:
        user_1_page.goto(get_required_env("BASE_URL") + launch_params)
        user_1_page.get_by_title("Настройка карточки").click()
        settings_dialog = user_1_page.get_by_role("dialog").filter(
            has=user_1_page.get_by_role(
                "button",
                name=tab_name,
                exact=True,
            )
        )
        settings_dialog.get_by_role(
            "button",
            name=tab_name,
            exact=True,
        ).click()

        target_name, target_id = (
            (fallback, fallback_id)
            if original_id == primary_id
            else (primary, primary_id)
        )
        # UI-020: image alt and visible label currently duplicate the
        # accessible name, so target the semantic button by its visible text.
        target_button = settings_dialog.get_by_role("button").filter(
            has_text=re.compile(rf"^{re.escape(target_name)}$")
        )
        with user_1_page.expect_response(
            lambda response: _is_customization_response(
                response,
                endpoint,
            )
        ) as selection_info:
            target_button.click()

        selection_response = selection_info.value
        selected_id = selection_response.request.post_data_json[profile_field]

        assert selection_response.status == 200, selection_response.text()
        assert selected_id == target_id
        assert get_user_profile(playwright, launch_params)[profile_field] == selected_id
    finally:
        select_profile_customization(
            playwright,
            launch_params,
            endpoint,
            profile_field,
            original_id,
        )
