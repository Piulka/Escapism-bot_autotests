from uuid import uuid4

import pytest
from playwright.sync_api import Playwright

from api_client import (
    delete_user_mail,
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
@pytest.mark.xfail(
    reason="API-005: reset clears mail contrary to the published contract",
    strict=True,
)
def test_reset_preserves_mail_outside_account_contract(
    playwright: Playwright,
) -> None:
    sender_launch_params = get_required_env("VK_LAUNCH_PARAMS_USER_1")
    recipient_launch_params = get_required_env("VK_LAUNCH_PARAMS_USER_2")
    mail_title = f"Reset persistence {uuid4().hex[:8]}"
    mail_id = None

    send_user_mail(
        playwright,
        sender_launch_params,
        {
            "to": "Тест 2",
            "title": mail_title,
            "content": "Письмо должно пережить account reset",
            "attachments": [],
        },
    )

    try:
        created_mail = next(
            message
            for message in get_user_mail(
                playwright,
                recipient_launch_params,
            )["items"]
            if message["title"] == mail_title
        )
        mail_id = created_mail["id"]

        reset_user(playwright, recipient_launch_params)

        assert any(
            message["id"] == mail_id
            for message in get_user_mail(
                playwright,
                recipient_launch_params,
            )["items"]
        )
    finally:
        if mail_id is not None and any(
            message["id"] == mail_id
            for message in get_user_mail(
                playwright,
                recipient_launch_params,
            )["items"]
        ):
            delete_user_mail(
                playwright,
                recipient_launch_params,
                mail_id,
            )
