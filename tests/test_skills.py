import re
from urllib.parse import urlsplit

import pytest
from playwright.sync_api import Page, Playwright, Response, expect

from api_client import (
    get_required_env,
    get_user_profile,
    inject_skill_experience,
)


SKILL_ID = "spec_sword"
XP_PER_CLICK = 10
CLICKS_TO_LEVEL_ONE = 10


def _is_skill_inject_response(response: Response) -> bool:
    return (
        response.request.method == "POST"
        and urlsplit(response.url).path == "/api/skills/inject"
    )


def _open_skills_from_footer(page: Page, launch_params: str) -> None:
    page.goto(get_required_env("BASE_URL") + launch_params)
    page.get_by_role("navigation").get_by_role(
        "button",
        name="Навыки",
        exact=True,
    ).click()
    expect(page.get_by_role("heading", name="Категории")).to_be_visible()


@pytest.mark.smoke
def test_level_up_sword_skill_with_learning_points(
    user_1_page: Page,
    playwright: Playwright,
) -> None:
    launch_params = get_required_env("VK_LAUNCH_PARAMS_USER_1")
    profile_before = get_user_profile(playwright, launch_params)
    learning_points_before = profile_before["learningPoints"]

    assert all(
        skill["id"] != SKILL_ID
        for skill in profile_before["skills"]
    ), "Sword skill must be unlearned after user reset"

    user_1_page.goto(get_required_env("BASE_URL") + launch_params)
    user_1_page.get_by_label("Навыки").click()
    user_1_page.get_by_role(
        "button",
        name=re.compile(r"^Оружие\s+Изучено 0%$"),
    ).click()
    user_1_page.get_by_role(
        "button",
        name=re.compile(r"^Клинки\s+0%$"),
    ).click()

    # TODO: replace .first with a skill-specific accessible name/data-testid.
    learn_sword_button = user_1_page.get_by_role(
        "button",
        name=f"Учить ({XP_PER_CLICK} LP)",
    ).first

    for _ in range(CLICKS_TO_LEVEL_ONE):
        with user_1_page.expect_response(
            _is_skill_inject_response,
        ) as response_info:
            learn_sword_button.click()

        response = response_info.value

        assert response.status == 200, (
            f"Skill inject request failed: {response.text()}"
        )
        assert response.request.post_data_json == {
            "skillId": SKILL_ID,
            "amount": XP_PER_CLICK,
            "useLp": True,
        }

    profile_after = get_user_profile(playwright, launch_params)
    sword_skill = next(
        skill
        for skill in profile_after["skills"]
        if skill["id"] == SKILL_ID
    )

    assert sword_skill["level"] == 1
    assert profile_after["learningPoints"] == (
        learning_points_before
        - XP_PER_CLICK * CLICKS_TO_LEVEL_ONE
    )


@pytest.mark.regression
def test_navigate_gathering_skill_tree_from_footer(
    page: Page,
) -> None:
    launch_params = get_required_env("VK_LAUNCH_PARAMS_USER_1")
    _open_skills_from_footer(page, launch_params)

    page.get_by_role(
        "button",
        name=re.compile(r"^Сбор\s+Изучено"),
    ).click()
    expect(page.get_by_role("heading", name="Сбор", level=2)).to_be_visible()

    page.get_by_role(
        "button",
        name=re.compile(r"^Лесоруб\s+0%$"),
    ).click()
    expect(
        page.get_by_role("heading", name="Лесоруб", level=2)
    ).to_be_visible()
    expect(
        page.get_by_role("heading", name="Владение топором")
    ).to_be_visible()
    expect(
        page.get_by_role("button", name="Учить (10 LP)")
    ).to_be_visible()

    page.get_by_role("button", name="Назад к списку").click()
    expect(page.get_by_role("heading", name="Сбор", level=2)).to_be_visible()
    expect(
        page.get_by_role("button", name="Лесоруб", exact=False)
    ).to_be_visible()

    page.get_by_role("button", name="Назад к категориям").click()
    expect(page.get_by_role("heading", name="Категории")).to_be_visible()


@pytest.mark.regression
def test_skill_learning_is_disabled_when_learning_points_are_insufficient(
    user_1_page: Page,
    playwright: Playwright,
) -> None:
    launch_params = get_required_env("VK_LAUNCH_PARAMS_USER_1")
    profile_initial = get_user_profile(playwright, launch_params)
    remaining_lp = XP_PER_CLICK - 1
    inject_skill_experience(
        playwright,
        launch_params,
        SKILL_ID,
        profile_initial["learningPoints"] - remaining_lp,
        use_lp=True,
    )
    profile_before_attempt = get_user_profile(playwright, launch_params)
    skill_before_attempt = next(
        skill
        for skill in profile_before_attempt["skills"]
        if skill["id"] == SKILL_ID
    )
    assert profile_before_attempt["learningPoints"] == remaining_lp

    user_1_page.goto(get_required_env("BASE_URL") + launch_params)
    user_1_page.get_by_label("Навыки").click()
    user_1_page.get_by_role(
        "button",
        name=re.compile(r"^Оружие\s+Изучено"),
    ).click()
    user_1_page.get_by_role(
        "button",
        name=re.compile(r"^Клинки\s+"),
    ).click()
    learn_button = user_1_page.get_by_role(
        "button",
        name=f"Учить ({XP_PER_CLICK} LP)",
    ).first
    expect(learn_button).to_be_visible()
    if learn_button.is_enabled():
        pytest.xfail(
            "UI-023: with insufficient LP the enabled learn button "
            "silently ignores the click"
        )
    expect(learn_button).to_be_disabled()

    profile_after_attempt = get_user_profile(playwright, launch_params)
    skill_after_attempt = next(
        skill
        for skill in profile_after_attempt["skills"]
        if skill["id"] == SKILL_ID
    )
    assert profile_after_attempt["learningPoints"] == remaining_lp
    assert skill_after_attempt["level"] == skill_before_attempt["level"]
    assert skill_after_attempt["xp"] == skill_before_attempt["xp"]


@pytest.mark.regression
@pytest.mark.parametrize(
    "viewport",
    [
        pytest.param({"width": 1280, "height": 720}, id="desktop"),
        pytest.param({"width": 390, "height": 844}, id="vk-mini-app"),
    ],
)
def test_skills_tree_controls_are_actionable_in_viewport(
    page: Page,
    viewport: dict[str, int],
) -> None:
    launch_params = get_required_env("VK_LAUNCH_PARAMS_USER_1")
    page.set_viewport_size(viewport)
    _open_skills_from_footer(page, launch_params)

    category_buttons = [
        page.get_by_role("button", name=re.compile(rf"^{category}\s+Изучено"))
        for category in (
            "Оружие",
            "Броня",
            "Сбор",
            "Обработка",
            "Ремесло",
        )
    ]
    for category_button in category_buttons:
        category_button.scroll_into_view_if_needed()
        expect(category_button).to_be_visible()
        expect(category_button).to_be_in_viewport()
        category_button.click(trial=True)

    category_buttons[2].click()
    lumberjack = page.get_by_role(
        "button",
        name=re.compile(r"^Лесоруб\s+0%$"),
    )
    lumberjack.scroll_into_view_if_needed()
    expect(lumberjack).to_be_in_viewport()
    lumberjack.click()

    branch_controls = [
        page.get_by_role("button", name="Учить (10 LP)"),
        page.get_by_role("button", name="Изучать"),
        page.get_by_role("button", name="Назад к списку"),
    ]
    for control in branch_controls:
        control.scroll_into_view_if_needed()
        expect(control).to_be_visible()
        expect(control).to_be_in_viewport()
        control.click(trial=True)
