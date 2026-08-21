import re
from urllib.parse import urlsplit
from uuid import uuid4

import pytest
from playwright.sync_api import Locator, Page, Playwright, Response, expect

from api_client import (
    claim_user_mail,
    delete_user_mail,
    get_required_env,
    get_user_inventory,
    get_user_mail,
    reset_user,
    send_user_mail,
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


def _is_mail_delete_response(response: Response, mail_id: str) -> bool:
    return (
        response.request.method == "DELETE"
        and urlsplit(response.url).path == f"/api/mail/{mail_id}"
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


def _open_mail_compose(page: Page, launch_params: str) -> None:
    page.goto(get_required_env("BASE_URL") + launch_params)
    page.get_by_label("Почта").click()
    page.get_by_role(
        "button",
        name="Отправить",
        exact=True,
    ).first.click()
    expect(
        page.get_by_placeholder("Имя игрока")
    ).to_be_visible()


def _open_attachment_picker(page: Page) -> Locator:
    page.get_by_role(
        "button",
        name="+ Добавить",
        exact=True,
    ).click()
    picker = page.get_by_role("dialog", name="Выберите предмет")
    expect(picker).to_be_visible()
    return picker


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
            exact=True,
        ).first.click()
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

        for index in ATTACHMENT_INVENTORY_INDEXES:
            item = sender_inventory_before[index]
            user_1_page.get_by_role(
                "button",
                name=f"Прикрепить {item['name']} ({item['quantity']})",
                exact=True,
            ).click()

        expect(
            user_1_page.get_by_text("Выбрано: 2 / 5", exact=True)
        ).to_be_visible()
        user_1_page.get_by_role(
            "button",
            name="Прикрепить",
            exact=True,
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

        mail_card = user_2_page.get_by_role(
            "button",
            name=f"{mail_title}, не прочитано",
            exact=True,
        )
        expect(mail_card).to_contain_text(f"От: {SENDER_NAME}")

        with user_2_page.expect_response(
            lambda response: _is_mail_response(
                response,
                "/api/mail/read",
            )
        ) as read_response_info:
            mail_card.click()

        read_response = read_response_info.value

        assert read_response.status == 200, (
            f"Mail read failed: {read_response.text()}"
        )
        assert read_response.request.post_data_json == {
            "mailId": created_mail_id,
        }
        expect(
            user_2_page.get_by_role(
                "button",
                name=f"{mail_title}, прочитано",
                exact=True,
            )
        ).to_have_count(1)
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


@pytest.mark.regression
@pytest.mark.parametrize(
    ("recipient", "content"),
    [
        pytest.param("", "Проверка обязательного получателя", id="no-recipient"),
        pytest.param(RECIPIENT_NAME, "", id="empty-mail"),
    ],
)
def test_mail_disables_submit_when_required_data_is_missing(
    page: Page,
    recipient: str,
    content: str,
) -> None:
    launch_params = get_required_env("VK_LAUNCH_PARAMS_USER_1")
    _open_mail_compose(page, launch_params)

    if recipient:
        page.get_by_placeholder("Имя игрока").fill(recipient)
    if content:
        page.get_by_placeholder("Текст сообщения...").fill(content)

    expect(
        page.get_by_role(
            "button",
            name="Отправить",
            exact=True,
        ).last
    ).to_be_disabled()


@pytest.mark.regression
@pytest.mark.parametrize(
    ("recipient", "expected_error"),
    [
        pytest.param(
            "Unknown recipient 12345",
            "Игрок с таким именем не найден.",
            id="unknown-recipient",
        ),
        pytest.param(
            SENDER_NAME,
            "Нельзя отправить письмо самому себе.",
            id="self-recipient",
        ),
    ],
)
def test_mail_rejects_invalid_recipient(
    page: Page,
    recipient: str,
    expected_error: str,
) -> None:
    launch_params = get_required_env("VK_LAUNCH_PARAMS_USER_1")
    _open_mail_compose(page, launch_params)
    page.get_by_placeholder("Имя игрока").fill(recipient)
    page.get_by_placeholder("Текст сообщения...").fill(
        "Проверка валидации получателя"
    )

    with page.expect_response(
        lambda response: _is_mail_response(
            response,
            "/api/mail/send",
        )
    ) as send_response_info:
        page.get_by_role(
            "button",
            name="Отправить",
            exact=True,
        ).last.click()

    send_response = send_response_info.value
    assert send_response.status == 400, (
        f"Invalid recipient was not rejected: {send_response.text()}"
    )
    assert send_response.json() == {
        "error": expected_error,
        "code": "VALIDATION_ERROR",
    }
    expect(page.get_by_text(expected_error, exact=True)).to_be_visible()


@pytest.mark.regression
def test_repeated_mail_claim_does_not_duplicate_attachment(
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
    mail_title = f"Idempotent claim {uuid4().hex[:8]}"
    item_id = "food_raw_1"
    sent_quantity = 1
    created_mail_id = None

    sender_quantities = _inventory_quantities(
        get_user_inventory(playwright, user_1_launch_params)
    )
    recipient_before = _inventory_quantities(
        get_user_inventory(playwright, user_2_launch_params)
    )
    assert sender_quantities[item_id] >= sent_quantity

    try:
        assert send_user_mail(
            playwright,
            user_1_launch_params,
            {
                "to": RECIPIENT_NAME,
                "title": mail_title,
                "content": "Проверка повторного получения вложения",
                "attachments": [
                    {
                        "type": "item",
                        "itemId": item_id,
                        "amount": sent_quantity,
                    }
                ],
            },
        ) == {"success": True}
        created_mail = _find_mail_by_title(
            get_user_mail(playwright, user_2_launch_params),
            mail_title,
        )
        created_mail_id = created_mail["id"]

        user_2_page.goto(
            get_required_env("BASE_URL") + user_2_launch_params
        )
        user_2_page.get_by_label("Почта").click()
        user_2_page.get_by_text(mail_title, exact=True).click()

        with user_2_page.expect_response(
            lambda response: _is_mail_response(
                response,
                "/api/mail/claim",
            )
        ) as first_claim_info:
            user_2_page.get_by_role(
                "button",
                name="Забрать вложения",
            ).click()

        first_claim = first_claim_info.value
        assert first_claim.status == 200, (
            f"Mail claim failed: {first_claim.text()}"
        )
        expect(
            user_2_page.get_by_role("button", name="Получено")
        ).to_be_disabled()

        inventory_after_first_claim = _inventory_quantities(
            get_user_inventory(playwright, user_2_launch_params)
        )
        assert inventory_after_first_claim[item_id] == (
            recipient_before[item_id] + sent_quantity
        )

        assert claim_user_mail(
            playwright,
            user_2_launch_params,
            created_mail_id,
        ) == {"success": True}
        inventory_after_second_claim = _inventory_quantities(
            get_user_inventory(playwright, user_2_launch_params)
        )
        assert inventory_after_second_claim == inventory_after_first_claim
    finally:
        if created_mail_id is not None:
            delete_user_mail(
                playwright,
                user_2_launch_params,
                created_mail_id,
            )
        reset_user(playwright, user_1_launch_params)
        reset_user(playwright, user_2_launch_params)


@pytest.mark.regression
@pytest.mark.parametrize(
    "viewport",
    [
        pytest.param({"width": 1280, "height": 720}, id="desktop"),
        pytest.param({"width": 390, "height": 844}, id="vk-mini-app"),
    ],
)
def test_mail_compose_controls_are_actionable_in_viewport(
    page: Page,
    viewport: dict[str, int],
) -> None:
    launch_params = get_required_env("VK_LAUNCH_PARAMS_USER_1")
    page.set_viewport_size(viewport)
    _open_mail_compose(page, launch_params)

    controls = [
        page.get_by_placeholder("Имя игрока"),
        page.get_by_placeholder("Тема письма"),
        page.get_by_placeholder("Текст сообщения..."),
        page.get_by_role("button", name="+ Добавить", exact=True),
        page.get_by_role("button", name="Назад", exact=True),
        page.get_by_role(
            "button",
            name="Отправить",
            exact=True,
        ).last,
    ]

    for control in controls:
        control.scroll_into_view_if_needed()
        expect(control).to_be_visible()
        expect(control).to_be_in_viewport()
        if control.is_enabled():
            control.click(trial=True)


@pytest.mark.regression
def test_mail_limits_attachments_and_allows_removal(
    page: Page,
    playwright: Playwright,
) -> None:
    launch_params = get_required_env("VK_LAUNCH_PARAMS_USER_1")
    inventory = get_user_inventory(playwright, launch_params)
    _open_mail_compose(page, launch_params)
    picker = _open_attachment_picker(page)

    assert len(inventory) >= 6
    for item in inventory[:5]:
        picker.get_by_role(
            "button",
            name=f"Прикрепить {item['name']} ({item['quantity']})",
            exact=True,
        ).click()

    expect(picker.get_by_text("Выбрано: 5 / 5", exact=True)).to_be_visible()
    sixth_item = inventory[5]
    picker.get_by_role(
        "button",
        name=(
            f"Прикрепить {sixth_item['name']} "
            f"({sixth_item['quantity']})"
        ),
        exact=True,
    ).click()
    expect(picker.get_by_text("Выбрано: 5 / 5", exact=True)).to_be_visible()

    picker.get_by_role(
        "button",
        name="Прикрепить",
        exact=True,
    ).click()
    expect(page.get_by_text("Вложения (5/5)", exact=True)).to_be_visible()

    remove_buttons = page.get_by_role(
        "button",
        name=re.compile(r"^Удалить вложение:"),
    )
    expect(remove_buttons).to_have_count(5)
    remove_buttons.first.click()

    expect(page.get_by_text("Вложения (4/5)", exact=True)).to_be_visible()
    expect(remove_buttons).to_have_count(4)


@pytest.mark.regression
def test_mail_compose_uses_documented_text_limits(page: Page) -> None:
    launch_params = get_required_env("VK_LAUNCH_PARAMS_USER_1")
    _open_mail_compose(page, launch_params)

    recipient = page.get_by_placeholder("Имя игрока")
    subject = page.get_by_placeholder("Тема письма")
    body = page.get_by_placeholder("Текст сообщения...")

    expect(recipient).to_have_attribute("maxlength", "30")
    expect(subject).to_have_attribute("maxlength", "120")
    expect(body).to_have_attribute("maxlength", "4000")
    for counter in ("0/30", "0/120", "0/4000"):
        expect(page.get_by_text(counter, exact=True)).to_be_visible()

    subject.fill("S" * 120)
    body.fill("B" * 4000)
    expect(page.get_by_text("120/120", exact=True)).to_be_visible()
    expect(page.get_by_text("4000/4000", exact=True)).to_be_visible()


@pytest.mark.regression
def test_mail_delete_requires_confirmation(
    page: Page,
    playwright: Playwright,
) -> None:
    sender_launch_params = get_required_env("VK_LAUNCH_PARAMS_USER_1")
    launch_params = get_required_env("VK_LAUNCH_PARAMS_USER_2")
    mail_title = f"Delete confirmation {uuid4().hex[:8]}"
    send_user_mail(
        playwright,
        sender_launch_params,
        {
            "to": RECIPIENT_NAME,
            "title": mail_title,
            "content": "Проверка подтверждения удаления",
            "attachments": [],
        },
    )
    message = _find_mail_by_title(
        get_user_mail(playwright, launch_params),
        mail_title,
    )

    try:
        page.goto(get_required_env("BASE_URL") + launch_params)
        page.get_by_label("Почта").click()
        page.get_by_role(
            "button",
            name=f"{mail_title}, не прочитано",
            exact=True,
        ).click()

        delete_button = page.get_by_role(
            "button",
            name="Удалить письмо",
            exact=True,
        )
        expect(delete_button).to_be_visible()
        delete_button.click()
        confirmation = page.get_by_role("dialog", name="Удаление письма")
        expect(confirmation).to_be_visible()
        expect(confirmation).to_contain_text(
            "Письмо будет удалено без возможности восстановления."
        )
        confirmation.get_by_role(
            "button",
            name="Отмена",
            exact=True,
        ).click()
        expect(confirmation).to_have_count(0)
        assert _find_mail_by_title(
            get_user_mail(playwright, launch_params),
            mail_title,
        )["id"] == message["id"]

        delete_button.click()
        confirmation = page.get_by_role("dialog", name="Удаление письма")
        expect(confirmation).to_be_visible()
        with page.expect_response(
            lambda response: _is_mail_delete_response(
                response,
                str(message["id"]),
            )
        ) as delete_response_info:
            confirmation.get_by_role(
                "button",
                name="Удалить",
                exact=True,
            ).click()

        assert delete_response_info.value.status == 200
        assert all(
            item["id"] != message["id"]
            for item in get_user_mail(playwright, launch_params)["items"]
        )
        expect(page.get_by_text(mail_title, exact=True)).to_have_count(0)
    finally:
        remaining_ids = {
            item["id"]
            for item in get_user_mail(playwright, launch_params)["items"]
        }
        if message["id"] in remaining_ids:
            delete_user_mail(playwright, launch_params, message["id"])


@pytest.mark.regression
def test_mail_changes_attachment_quantity_within_available_stack(
    page: Page,
    playwright: Playwright,
) -> None:
    launch_params = get_required_env("VK_LAUNCH_PARAMS_USER_1")
    inventory = get_user_inventory(playwright, launch_params)
    item_index = next(
        index
        for index, item in enumerate(inventory)
        if item["id"] == "food_raw_1"
    )
    available_quantity = inventory[item_index]["quantity"]

    assert available_quantity >= 2
    _open_mail_compose(page, launch_params)
    picker = _open_attachment_picker(page)

    item = inventory[item_index]
    picker.get_by_role(
        "button",
        name=f"Прикрепить {item['name']} ({item['quantity']})",
        exact=True,
    ).click()
    picker.get_by_role(
        "button",
        name="Прикрепить",
        exact=True,
    ).click()

    quantity = page.get_by_text(
        f"x{available_quantity}",
        exact=True,
    )
    expect(quantity).to_be_visible()
    page.get_by_role("button", name="−", exact=True).click()
    expect(
        page.get_by_text(
            f"x{available_quantity - 1}",
            exact=True,
        )
    ).to_be_visible()
    page.get_by_role("button", name="+", exact=True).click()
    expect(quantity).to_be_visible()
