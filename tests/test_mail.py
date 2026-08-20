import re
from urllib.parse import urlsplit
from uuid import uuid4

import pytest
from playwright.sync_api import Page, Playwright, Response, expect

from api_client import (
    delete_user_mail,
    get_required_env,
    get_user_inventory,
    get_user_mail,
)


RECIPIENT_NAME = "Тест 2"
SENDER_NAME = "Тест 1"
MAIL_CONTENT = "Проверка отправки и получения вложений"
ATTACHMENTS = {
    "food_raw_1": 5,
    "pot_hp_t2": 3,
}
ATTACHMENT_INVENTORY_INDEXES = (6, 8)


def _is_mail_response(response: Response, path: str) -> bool:
    return (
        response.request.method == "POST"
        and urlsplit(response.url).path == path
    )


def _inventory_quantities(
    inventory: list[dict],
) -> dict[str, int]:
    return {
        item["id"]: item["quantity"]
        for item in inventory
    }


def _find_mail_by_title(
    mail: dict,
    title: str,
) -> dict:
    return next(
        message
        for message in mail["items"]
        if message["title"] == title
    )


@pytest.mark.smoke
def test_send_and_claim_mail_attachments(
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
    mail_title = f"Smoke mail {uuid4().hex[:8]}"
    created_mail_id = None

    sender_inventory_before = get_user_inventory(
        playwright,
        user_1_launch_params,
    )
    recipient_inventory_before = get_user_inventory(
        playwright,
        user_2_launch_params,
    )
    recipient_mail_before = get_user_mail(
        playwright,
        user_2_launch_params,
    )
    unread_before = sum(
        not message["isRead"]
        for message in recipient_mail_before["items"]
    )

    sender_quantities_before = _inventory_quantities(
        sender_inventory_before
    )
    recipient_quantities_before = _inventory_quantities(
        recipient_inventory_before
    )

    assert {
        sender_inventory_before[index]["id"]
        for index in ATTACHMENT_INVENTORY_INDEXES
    } == set(ATTACHMENTS)
    assert all(
        sender_quantities_before[item_id] == quantity
        for item_id, quantity in ATTACHMENTS.items()
    )

    try:
        user_1_page.goto(
            get_required_env("BASE_URL") + user_1_launch_params
        )
        user_1_page.get_by_label("Почта").click()
        user_1_page.get_by_role(
            "button",
            name="Отправить",
        ).click()
        user_1_page.get_by_placeholder("Имя игрока").fill(
            RECIPIENT_NAME
        )
        user_1_page.get_by_placeholder("Тема письма").fill(
            mail_title
        )
        user_1_page.get_by_placeholder(
            "Текст сообщения..."
        ).fill(MAIL_CONTENT)
        user_1_page.get_by_role(
            "button",
            name="+ Добавить",
        ).click()

        # TODO: add accessible names/data-testid with item IDs to the cards.
        attachment_cards = user_1_page.locator("div.aspect-square")
        for index in ATTACHMENT_INVENTORY_INDEXES:
            attachment_cards.nth(index).click()

        expect(
            user_1_page.get_by_text("Выбрано: 2 / 5", exact=True)
        ).to_be_visible()
        user_1_page.get_by_role(
            "button",
            name="Прикрепить",
        ).click()
        expect(
            user_1_page.get_by_text("Вложения (2/5)", exact=True)
        ).to_be_visible()

        with user_1_page.expect_response(
            lambda response: _is_mail_response(
                response,
                "/api/mail/send",
            )
        ) as send_response_info:
            user_1_page.get_by_role(
                "button",
                name="Отправить",
            ).last.click()

        send_response = send_response_info.value
        send_payload = send_response.request.post_data_json

        assert send_response.status == 200, (
            f"Mail send failed: {send_response.text()}"
        )
        assert send_payload["to"] == RECIPIENT_NAME
        assert send_payload["title"] == mail_title
        assert send_payload["content"] == MAIL_CONTENT
        assert {
            attachment["item"]["id"]: attachment["amount"]
            for attachment in send_payload["attachments"]
        } == ATTACHMENTS

        sender_inventory_after = get_user_inventory(
            playwright,
            user_1_launch_params,
        )
        sender_quantities_after = _inventory_quantities(
            sender_inventory_after
        )

        for item_id, sent_quantity in ATTACHMENTS.items():
            assert sender_quantities_after.get(item_id, 0) == (
                sender_quantities_before[item_id] - sent_quantity
            )

        recipient_mail_after_send = get_user_mail(
            playwright,
            user_2_launch_params,
        )
        created_mail = _find_mail_by_title(
            recipient_mail_after_send,
            mail_title,
        )
        created_mail_id = created_mail["id"]

        assert created_mail["sender"] == SENDER_NAME
        assert created_mail["content"] == MAIL_CONTENT
        assert created_mail["isRead"] is False
        assert created_mail["hasClaimed"] is False
        assert {
            attachment["item"]["id"]: attachment["amount"]
            for attachment in created_mail["attachments"]
        } == ATTACHMENTS

        user_2_page.goto(
            get_required_env("BASE_URL") + user_2_launch_params
        )
        user_2_page.get_by_label("Почта").click()
        expect(
            user_2_page.get_by_role(
                "button",
                name=re.compile(
                    rf"^Входящие\s*{unread_before + 1}$"
                ),
            )
        ).to_be_visible()

        mail_title_element = user_2_page.get_by_text(
            mail_title,
            exact=True,
        )
        expect(mail_title_element).to_be_visible()

        # TODO: expose unread state through aria/data-testid.
        mail_card = mail_title_element.locator(
            "xpath=ancestor::div[contains(@class, 'cursor-pointer')][1]"
        )
        unread_indicator = mail_card.locator("div.bg-red-500")
        expect(mail_card).to_contain_text(f"От: {SENDER_NAME}")
        expect(unread_indicator).to_be_visible()

        with user_2_page.expect_response(
            lambda response: _is_mail_response(
                response,
                "/api/mail/read",
            )
        ) as read_response_info:
            mail_title_element.click()

        read_response = read_response_info.value

        assert read_response.status == 200, (
            f"Mail read failed: {read_response.text()}"
        )
        assert read_response.request.post_data_json == {
            "mailId": created_mail_id,
        }
        expect(unread_indicator).to_have_count(0)
        expect(
            user_2_page.get_by_role(
                "button",
                name="Входящие",
            )
        ).to_be_visible()
        expect(
            user_2_page.get_by_role(
                "heading",
                name=mail_title,
            ).last
        ).to_be_visible()
        expect(
            user_2_page.get_by_text(f"От: {SENDER_NAME}", exact=True).last
        ).to_be_visible()
        expect(
            user_2_page.get_by_text(MAIL_CONTENT, exact=True)
        ).to_be_visible()

        mail_after_read = _find_mail_by_title(
            get_user_mail(playwright, user_2_launch_params),
            mail_title,
        )
        assert mail_after_read["isRead"] is True

        with user_2_page.expect_response(
            lambda response: _is_mail_response(
                response,
                "/api/mail/claim",
            )
        ) as claim_response_info:
            user_2_page.get_by_role(
                "button",
                name="Забрать вложения",
            ).click()

        claim_response = claim_response_info.value

        assert claim_response.status == 200, (
            f"Mail claim failed: {claim_response.text()}"
        )
        assert claim_response.request.post_data_json == {
            "mailId": created_mail_id,
        }
        expect(
            user_2_page.get_by_role(
                "button",
                name="Получено",
            )
        ).to_be_disabled()

        mail_after_claim = _find_mail_by_title(
            get_user_mail(playwright, user_2_launch_params),
            mail_title,
        )
        assert mail_after_claim["hasClaimed"] is True

        recipient_inventory_after = get_user_inventory(
            playwright,
            user_2_launch_params,
        )
        recipient_quantities_after = _inventory_quantities(
            recipient_inventory_after
        )

        for item_id, received_quantity in ATTACHMENTS.items():
            assert recipient_quantities_after[item_id] == (
                recipient_quantities_before[item_id]
                + received_quantity
            )
    finally:
        if created_mail_id is not None:
            delete_user_mail(
                playwright,
                user_2_launch_params,
                created_mail_id,
            )
