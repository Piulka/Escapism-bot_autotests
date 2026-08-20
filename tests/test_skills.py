import re
from urllib.parse import urlsplit

import pytest
from playwright.sync_api import Page, Playwright, Response

from api_client import get_required_env, get_user_profile


SKILL_ID = "spec_sword"
XP_PER_CLICK = 10
CLICKS_TO_LEVEL_ONE = 10


def _is_skill_inject_response(response: Response) -> bool:
    return (
        response.request.method == "POST"
        and urlsplit(response.url).path == "/api/skills/inject"
    )


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
