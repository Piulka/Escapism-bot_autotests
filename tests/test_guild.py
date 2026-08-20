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
    apply_to_guild,
    attempt_kick_guild_member,
    create_user_guild,
    decide_guild_application,
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


def _open_create_guild_dialog(page: Page, launch_params: str) -> Locator:
    page.goto(get_required_env("BASE_URL") + launch_params)
    page.get_by_label("Гильдия").click()
    page.get_by_role(
        "button",
        name="Создать свою гильдию",
    ).click()
    dialog = page.get_by_role("dialog", name="Создание гильдии")
    expect(dialog).to_be_visible()
    return dialog


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


def _leave_guild_users(
    playwright: Playwright,
    *launch_params_values: str,
) -> None:
    cleanup_error = None
    for launch_params in launch_params_values:
        try:
            _leave_guild_if_present(playwright, launch_params)
        except Exception as error:
            cleanup_error = cleanup_error or error

    if cleanup_error is not None:
        raise cleanup_error


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
    _leave_guild_users(
        playwright,
        user_2_launch_params,
        user_1_launch_params,
    )

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
        _leave_guild_users(
            playwright,
            user_2_launch_params,
            user_1_launch_params,
        )


@pytest.mark.regression
@pytest.mark.parametrize(
    ("guild_name", "guild_tag", "expected_error"),
    [
        pytest.param(
            "",
            "AB",
            "Название гильдии: от 2 до 20 символов.",
            id="empty-name",
        ),
        pytest.param(
            "A",
            "AB",
            "Название гильдии: от 2 до 20 символов.",
            id="short-name",
        ),
        pytest.param(
            "Valid name",
            "A",
            "Тег: 2-4 латинские буквы или цифры (например, DAWN).",
            id="short-tag",
        ),
        pytest.param(
            "Valid name",
            "A!",
            "Тег: 2-4 латинские буквы или цифры (например, DAWN).",
            id="invalid-tag-character",
        ),
    ],
)
def test_create_guild_rejects_invalid_name_and_tag(
    page: Page,
    playwright: Playwright,
    guild_name: str,
    guild_tag: str,
    expected_error: str,
) -> None:
    launch_params = get_required_env("VK_LAUNCH_PARAMS_USER_1")
    _leave_guild_if_present(playwright, launch_params)
    dialog = _open_create_guild_dialog(page, launch_params)
    dialog.get_by_placeholder(
        "Например: Стражи Рассвета"
    ).fill(guild_name)
    dialog.get_by_placeholder("Например: DAWN").fill(guild_tag)

    dialog.get_by_role(
        "button",
        name="Создать гильдию",
    ).click()

    expect(page.get_by_text(expected_error, exact=True)).to_be_visible()
    expect(dialog).to_be_visible()


@pytest.mark.regression
def test_create_guild_normalizes_limits_and_cancel_keeps_state(
    page: Page,
    playwright: Playwright,
) -> None:
    launch_params = get_required_env("VK_LAUNCH_PARAMS_USER_1")
    _leave_guild_if_present(playwright, launch_params)
    dialog = _open_create_guild_dialog(page, launch_params)
    name_input = dialog.get_by_placeholder(
        "Например: Стражи Рассвета"
    )
    tag_input = dialog.get_by_placeholder("Например: DAWN")

    name_input.fill("A" * 21)
    tag_input.fill("abcde")
    expect(name_input).to_have_value("A" * 20)
    expect(tag_input).to_have_value("ABCD")

    dialog.get_by_role("button", name="Отмена").click()
    expect(dialog).to_have_count(0)
    assert get_user_guild(playwright, launch_params) == []


@pytest.mark.regression
@pytest.mark.parametrize(
    "viewport",
    [
        pytest.param({"width": 1280, "height": 720}, id="desktop"),
        pytest.param({"width": 390, "height": 844}, id="vk-mini-app"),
    ],
)
def test_create_guild_controls_are_actionable_in_viewport(
    page: Page,
    playwright: Playwright,
    viewport: dict[str, int],
) -> None:
    launch_params = get_required_env("VK_LAUNCH_PARAMS_USER_1")
    _leave_guild_if_present(playwright, launch_params)
    page.set_viewport_size(viewport)
    dialog = _open_create_guild_dialog(page, launch_params)

    controls = [
        dialog.get_by_placeholder("Например: Стражи Рассвета"),
        dialog.get_by_placeholder("Например: DAWN"),
        dialog.get_by_role("button", name="Отмена"),
        dialog.get_by_role("button", name="Создать гильдию"),
    ]
    for control in controls:
        control.scroll_into_view_if_needed()
        expect(control).to_be_visible()
        expect(control).to_be_in_viewport()

    for button_name in ("Отмена", "Создать гильдию"):
        dialog.get_by_role("button", name=button_name).click(trial=True)


@pytest.mark.regression
@pytest.mark.xfail(
    reason="UI-011: rejected guild application remains submitted in catalog",
    strict=True,
)
def test_reject_reapply_accept_and_leave_guild(
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
    guild_name = f"Regression {unique_value[:6]}"
    guild_tag = unique_value[-4:].upper()

    _leave_guild_users(
        playwright,
        user_2_launch_params,
        user_1_launch_params,
    )
    create_user_guild(
        playwright,
        user_1_launch_params,
        guild_name,
        guild_tag,
    )

    try:
        guild_heading = _open_guild_catalog_until_visible(
            user_2_page,
            user_2_launch_params,
            guild_name,
        )
        guild_card = guild_heading.locator(
            "xpath=ancestor::div[contains(@class, 'rounded-2xl')][1]"
        )

        with user_2_page.expect_response(
            lambda response: _is_post_response(
                response,
                "/api/guild/join",
            )
        ) as first_join_info:
            guild_card.get_by_role(
                "button",
                name="Подать заявку",
            ).click()
        assert first_join_info.value.status == 200

        first_application = get_guild_applications(
            playwright,
            user_1_launch_params,
        )[0]
        applicant = _open_applications_until_visible(
            user_1_page,
            user_1_launch_params,
            MEMBER_NAME,
        )
        application_card = applicant.locator(
            "xpath=ancestor::div[contains(@class, 'rounded-2xl')][1]"
        )
        reject_path = (
            f"/api/guild/applications/{first_application['id']}/reject"
        )
        with user_1_page.expect_response(
            lambda response: _is_post_response(response, reject_path)
        ) as reject_info:
            application_card.get_by_role(
                "button",
                name="Отклонить",
            ).click()
        assert reject_info.value.status == 200
        expect(applicant).to_have_count(0)
        assert get_guild_applications(
            playwright,
            user_1_launch_params,
        ) == []

        guild_heading = _open_guild_catalog_until_visible(
            user_2_page,
            user_2_launch_params,
            guild_name,
        )
        guild_card = guild_heading.locator(
            "xpath=ancestor::div[contains(@class, 'rounded-2xl')][1]"
        )
        reapply_button = guild_card.get_by_role(
            "button",
            name="Подать заявку",
        )
        expect(reapply_button).to_be_visible(timeout=5_000)
        with user_2_page.expect_response(
            lambda response: _is_post_response(
                response,
                "/api/guild/join",
            )
        ) as second_join_info:
            reapply_button.click()
        assert second_join_info.value.status == 200

        second_application = get_guild_applications(
            playwright,
            user_1_launch_params,
        )[0]
        applicant = _open_applications_until_visible(
            user_1_page,
            user_1_launch_params,
            MEMBER_NAME,
        )
        application_card = applicant.locator(
            "xpath=ancestor::div[contains(@class, 'rounded-2xl')][1]"
        )
        accept_path = (
            f"/api/guild/applications/{second_application['id']}/accept"
        )
        with user_1_page.expect_response(
            lambda response: _is_post_response(response, accept_path)
        ) as accept_info:
            application_card.get_by_role(
                "button",
                name="Принять",
            ).click()
        assert accept_info.value.status == 200
        assert {member["name"] for member in get_guild_members(
            playwright,
            user_1_launch_params,
        )} == {LEADER_NAME, MEMBER_NAME}

        user_2_page.goto(
            get_required_env("BASE_URL") + user_2_launch_params + "#/guild"
        )
        expect(
            user_2_page.get_by_role("heading", name=guild_name)
        ).to_be_visible()
        user_2_page.get_by_role(
            "button",
            name="Покинуть гильдию",
        ).click()
        with user_2_page.expect_response(
            lambda response: _is_post_response(
                response,
                "/api/guild/leave",
            )
        ) as leave_info:
            user_2_page.get_by_role(
                "button",
                name="Да, покинуть",
            ).click()
        assert leave_info.value.status == 200
        assert get_user_guild(playwright, user_2_launch_params) == []
        assert {member["name"] for member in get_guild_members(
            playwright,
            user_1_launch_params,
        )} == {LEADER_NAME}
    finally:
        _leave_guild_users(
            playwright,
            user_2_launch_params,
            user_1_launch_params,
        )


@pytest.mark.regression
def test_regular_guild_member_cannot_use_leader_actions(
    user_2_page: Page,
    reset_user_1: None,
    playwright: Playwright,
) -> None:
    user_1_launch_params = get_required_env(
        "VK_LAUNCH_PARAMS_USER_1"
    )
    user_2_launch_params = get_required_env(
        "VK_LAUNCH_PARAMS_USER_2"
    )
    unique_value = uuid4().hex
    guild_name = f"Roles {unique_value[:6]}"
    guild_tag = unique_value[-4:].upper()

    _leave_guild_users(
        playwright,
        user_2_launch_params,
        user_1_launch_params,
    )
    create_user_guild(
        playwright,
        user_1_launch_params,
        guild_name,
        guild_tag,
    )

    try:
        guild = get_user_guild(playwright, user_1_launch_params)
        apply_to_guild(
            playwright,
            user_2_launch_params,
            guild["id"],
        )
        application = get_guild_applications(
            playwright,
            user_1_launch_params,
        )[0]
        decide_guild_application(
            playwright,
            user_1_launch_params,
            application["id"],
            "accept",
        )

        member_guild = get_user_guild(
            playwright,
            user_2_launch_params,
        )
        members_before = get_guild_members(
            playwright,
            user_2_launch_params,
        )
        leader = next(
            member for member in members_before
            if member["role"] == "leader"
        )
        assert member_guild["myRole"] == "member"

        user_2_page.goto(
            get_required_env("BASE_URL")
            + user_2_launch_params
            + "#/guild"
        )
        expect(
            user_2_page.get_by_role("heading", name=guild_name)
        ).to_be_visible()
        expect(
            user_2_page.get_by_role("button", name=re.compile(r"^Заявки"))
        ).to_have_count(0)
        expect(
            user_2_page.locator("button:has(svg.lucide-pencil)")
        ).to_have_count(0)

        kick_status, kick_body = attempt_kick_guild_member(
            playwright,
            user_2_launch_params,
            leader["unitId"],
        )
        assert kick_status == 400
        assert kick_body == {
            "error": "Недостаточно прав.",
            "code": "VALIDATION_ERROR",
        }
        assert get_guild_members(
            playwright,
            user_2_launch_params,
        ) == members_before
    finally:
        _leave_guild_users(
            playwright,
            user_2_launch_params,
            user_1_launch_params,
        )
