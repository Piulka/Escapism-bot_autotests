import re
from urllib.parse import urlsplit
from uuid import uuid4

import pytest
from playwright.sync_api import (
    Locator,
    Page,
    Playwright,
    Response,
    expect,
)

from api_client import (
    get_guild_applications,
    get_guild_members,
    get_required_env,
    get_user_guild,
    leave_guild,
)


LEADER_NAME = "Тест 1"
MEMBER_NAME = "Тест 2"


def _is_post_response(response: Response, path: str) -> bool:
    return (
        response.request.method == "POST"
        and urlsplit(response.url).path == path
    )


def _reload_and_get_member(page: Page, name: str) -> Locator:
    page.reload()
    member_name = page.locator("#scroll-container").get_by_text(
        name,
        exact=True,
    ).first
    expect(member_name).to_be_visible()
    return member_name


def _open_applications_until_visible(
    page: Page,
    launch_params: str,
    applicant_name: str,
) -> Locator:
    guild_url = get_required_env("BASE_URL") + launch_params + "#/guild"
    page.goto(guild_url)
    page.get_by_role("button", name="Состав").click()
    page.get_by_role("button", name=re.compile(r"^Заявки")).click()
    applicant = page.get_by_text(applicant_name, exact=True)
    expect(applicant).to_be_visible()
    return applicant


def _open_guild_catalog_until_visible(
    page: Page,
    launch_params: str,
    guild_name: str,
) -> Locator:
    guilds_url = (
        get_required_env("BASE_URL") + launch_params + "#/guilds"
    )

    page.goto(guilds_url)
    guild_heading = page.get_by_role(
        "heading",
        name=guild_name,
    )
    expect(guild_heading).to_be_visible()
    return guild_heading


def _leave_guild_if_present(
    playwright: Playwright,
    launch_params: str,
) -> None:
    if get_user_guild(playwright, launch_params) == []:
        return

    leave_guild(playwright, launch_params)
    assert get_user_guild(playwright, launch_params) == []


@pytest.mark.smoke
def test_create_guild_accept_member_and_kick(
    user_1_page: Page,
    user_2_page: Page,
    playwright: Playwright,
) -> None:
    user_1_launch_params = get_required_env(
        "VK_LAUNCH_PARAMS_USER_1"
    )
    user_2_launch_params = get_required_env(
        "VK_LAUNCH_PARAMS_USER_2"
    )
    unique_value = uuid4().hex
    guild_name = f"Smoke {unique_value[:6]}"
    guild_tag = unique_value[-4:].upper()

    # Reset does not clear guild membership. Recover leftovers from an aborted
    # previous run before creating this test's isolated state.
    _leave_guild_if_present(playwright, user_2_launch_params)
    _leave_guild_if_present(playwright, user_1_launch_params)

    try:
        user_1_page.goto(
            get_required_env("BASE_URL") + user_1_launch_params
        )
        user_1_page.get_by_label("Гильдия").click()
        user_1_page.get_by_role(
            "button",
            name="Создать свою гильдию",
        ).click()
        user_1_page.get_by_placeholder(
            "Например: Стражи Рассвета"
        ).fill(guild_name)
        user_1_page.get_by_placeholder(
            "Например: DAWN"
        ).fill(guild_tag)

        with user_1_page.expect_response(
            lambda response: _is_post_response(
                response,
                "/api/guild/create",
            )
        ) as create_response_info:
            user_1_page.get_by_role(
                "button",
                name="Создать гильдию",
            ).click()

        create_response = create_response_info.value

        assert create_response.status == 200, (
            f"Guild creation failed: {create_response.text()}"
        )
        assert create_response.request.post_data_json == {
            "name": guild_name,
            "tag": guild_tag,
        }
        guild_heading = _open_guild_catalog_until_visible(
            user_2_page,
            user_2_launch_params,
            guild_name,
        )
        guild_card = guild_heading.locator(
            "xpath=ancestor::div[contains(@class, 'rounded-2xl')][1]"
        )
        expect(guild_card).to_contain_text(f"[{guild_tag}]")
        expect(guild_card).to_contain_text(LEADER_NAME)

        with user_2_page.expect_response(
            lambda response: _is_post_response(
                response,
                "/api/guild/join",
            )
        ) as join_response_info:
            guild_card.get_by_role(
                "button",
                name="Подать заявку",
            ).click()

        join_response = join_response_info.value

        assert join_response.status == 200, (
            f"Guild application failed: {join_response.text()}"
        )
        join_payload = join_response.request.post_data_json
        guild_id = join_payload["guildId"]
        assert isinstance(guild_id, int)
        expect(
            guild_card.get_by_role(
                "button",
                name="Заявка подана",
            )
        ).to_be_disabled()

        applications = get_guild_applications(
            playwright,
            user_1_launch_params,
        )
        application = next(
            item
            for item in applications
            if item["name"] == MEMBER_NAME
        )

        applicant_name = _open_applications_until_visible(
            user_1_page,
            user_1_launch_params,
            MEMBER_NAME,
        )
        applicant_card = applicant_name.locator(
            "xpath=ancestor::div[contains(@class, 'rounded-2xl')][1]"
        )
        accept_path = (
            f"/api/guild/applications/{application['id']}/accept"
        )
        with user_1_page.expect_response(
            lambda response: _is_post_response(
                response,
                accept_path,
            )
        ) as accept_response_info:
            applicant_card.get_by_role(
                "button",
                name="Принять",
            ).click()

        accept_response = accept_response_info.value

        assert accept_response.status == 200, (
            f"Guild application acceptance failed: "
            f"{accept_response.text()}"
        )
        expect(applicant_name).to_have_count(0)
        expect(
            user_1_page.get_by_text(
                "Нет активных заявок",
                exact=True,
            )
        ).to_be_visible()
        assert get_guild_applications(
            playwright,
            user_1_launch_params,
        ) == []

        members = get_guild_members(
            playwright,
            user_1_launch_params,
        )
        member = next(
            item
            for item in members
            if item["name"] == MEMBER_NAME
        )

        assert member["role"] == "member"

        member_name = _reload_and_get_member(
            user_1_page,
            MEMBER_NAME,
        )

        user_2_page.reload()
        my_guild_link = user_2_page.get_by_role(
            "link",
            name="Моя гильдия",
        )
        expect(my_guild_link).to_be_visible()
        my_guild_link.click()
        expect(
            user_2_page.get_by_role(
                "heading",
                name="Моя гильдия",
            ).first
        ).to_be_visible()
        expect(
            user_2_page.get_by_role(
                "heading",
                name=guild_name,
            )
        ).to_be_visible()

        # TODO: make guild member rows accessible buttons.
        member_name.click()
        expect(
            user_1_page.get_by_role(
                "heading",
                name=MEMBER_NAME,
            )
        ).to_be_visible()
        user_1_page.get_by_role(
            "button",
            name="Исключить из гильдии",
        ).click()
        expect(
            user_1_page.get_by_text(
                re.compile(rf"исключить игрока {MEMBER_NAME}"),
            )
        ).to_be_visible()

        with user_1_page.expect_response(
            lambda response: _is_post_response(
                response,
                "/api/guild/kick",
            )
        ) as kick_response_info:
            user_1_page.get_by_role(
                "button",
                name="Да, исключить",
            ).click()

        kick_response = kick_response_info.value

        assert kick_response.status == 200, (
            f"Guild member kick failed: {kick_response.text()}"
        )
        assert kick_response.request.post_data_json == {
            "unitId": member["unitId"],
        }
        expect(member_name).to_have_count(0)
        user_2_page.reload()
        expect(
            user_2_page.get_by_role(
                "heading",
                name="Поиск гильдии",
            )
        ).to_be_visible()
        expect(
            user_2_page.get_by_text(
                "Вы пока не состоите в гильдии. "
                "Выберите подходящую и подайте заявку.",
                exact=True,
            )
        ).to_be_visible()
    finally:
        cleanup_error = None
        for launch_params in (
            user_2_launch_params,
            user_1_launch_params,
        ):
            try:
                _leave_guild_if_present(playwright, launch_params)
            except Exception as error:
                cleanup_error = cleanup_error or error

        if cleanup_error is not None:
            raise cleanup_error
