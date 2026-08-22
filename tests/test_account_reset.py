from uuid import uuid4

import pytest
from playwright.sync_api import Playwright

from api_client import (
    get_required_env,
    get_user_inventory,
    get_user_mail,
    get_user_profile,
    get_user_warehouse,
    reset_user,
    send_user_mail,
)


@pytest.mark.regression
def test_reset_restores_documented_account_state(
    playwright: Playwright,
) -> None:
    launch_params = get_required_env("VK_LAUNCH_PARAMS_USER_2")

    reset_result = reset_user(playwright, launch_params)
    profile = get_user_profile(playwright, launch_params)
    inventory = get_user_inventory(playwright, launch_params)

    assert reset_result == {
        "success": True,
        "granted": {
            "quants": 5000,
            "fragments": 200,
            "learningPoints": 450,
            "items": 15,
            "recipes": 3,
        },
    }
    assert profile["currencies"] == {"quants": 5000, "fragments": 200}
    assert profile["learningPoints"] == 450
    equipment = profile["equipment"]
    assert all(
        item is None
        for slot, item in equipment.items()
        if slot != "quickSlots"
    )
    assert all(item is None for item in equipment["quickSlots"])
    assert get_user_warehouse(playwright, launch_params) == []
    assert {item["id"]: item["quantity"] for item in inventory} == {
        "eq_wep_t1": 1,
        "eq_off_t1": 1,
        "eq_head_t1": 1,
        "eq_body_t1": 1,
        "eq_legs_t1": 1,
        "eq_boots_t1": 1,
        "tool_pick_t1": 1,
        "food_raw_1": 5,
        "pot_hp_t2": 3,
    }


@pytest.mark.regression
def test_reset_replaces_mail_with_documented_seed_messages(
    playwright: Playwright,
) -> None:
    sender_launch_params = get_required_env("VK_LAUNCH_PARAMS_USER_1")
    recipient_launch_params = get_required_env("VK_LAUNCH_PARAMS_USER_2")
    mail_title = f"Reset persistence {uuid4().hex[:8]}"
    send_user_mail(
        playwright,
        sender_launch_params,
        {
            "to": "Тест 2",
            "title": mail_title,
            "content": "Письмо должно быть удалено account reset",
            "attachments": [],
        },
    )

    assert any(
        message["title"] == mail_title
        for message in get_user_mail(
            playwright,
            recipient_launch_params,
        )["items"]
    )

    reset_user(playwright, recipient_launch_params)
    seeded_mail = get_user_mail(
        playwright,
        recipient_launch_params,
    )["items"]

    assert len(seeded_mail) == 5
    assert {message["title"] for message in seeded_mail} == {
        "Добро пожаловать в Башню!",
        "Выплата за исследование",
        "Подарок за вступление",
        "Свитки древних знаний",
        "Приглашение в поход",
    }
    assert all(message["title"] != mail_title for message in seeded_mail)
