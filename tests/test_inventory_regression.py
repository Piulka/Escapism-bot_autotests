import re

import pytest
from playwright.sync_api import Locator, Page, Playwright, expect

from api_client import (
    equip_inventory_item,
    get_required_env,
    get_user_inventory,
    get_user_profile,
    reset_user,
    unequip_inventory_item,
)


EQUIPMENT_TYPES = {
    "Голова",
    "Тело",
    "Ноги",
    "Обувь",
    "Оружие",
    "Вторая рука",
    "Инструмент",
}
FOOD_TYPES = {"Еда", "Расходник"}
DETAIL_ITEM_ID = "eq_wep_t1"


@pytest.fixture(scope="module", autouse=True)
def reset_inventory_regression_user(playwright: Playwright) -> None:
    reset_user(
        playwright,
        get_required_env("VK_LAUNCH_PARAMS_USER_1"),
    )


def _open_inventory(page: Page, launch_params: str) -> None:
    page.goto(get_required_env("BASE_URL") + launch_params)
    page.get_by_role("button", name="Сумка", exact=True).click()
    expect(page.get_by_role("heading", name="Инвентарь")).to_be_visible()


def _filter_button(page: Page) -> Locator:
    return page.get_by_role("button", name="Фильтры", exact=True)


def _expect_filtered_items(
    page: Page,
    inventory: list[dict],
    expected_item_ids: set[str],
) -> None:
    for item in inventory:
        item_card = page.get_by_role(
            "button",
            name=item["name"],
            exact=True,
        )
        if item["id"] in expected_item_ids:
            expect(item_card).to_be_visible()
        else:
            expect(item_card).to_have_count(0)


def _open_item_dialog(page: Page, item_name: str) -> Locator:
    page.get_by_role("button", name=item_name, exact=True).click()
    item_heading = page.get_by_role("heading", name=item_name, exact=True)
    item_dialog = item_heading.locator(
        "xpath=ancestor::*[@role='dialog'][1]"
    )
    expect(item_dialog).to_be_visible()
    return item_dialog


@pytest.mark.regression
def test_filter_inventory_by_tier_and_remove_filter(
    page: Page,
    playwright: Playwright,
) -> None:
    launch_params = get_required_env("VK_LAUNCH_PARAMS_USER_1")
    inventory = get_user_inventory(playwright, launch_params)
    tier = 2
    expected_item_ids = {
        item["id"]
        for item in inventory
        if item["tier"] == tier
    }

    assert expected_item_ids
    _open_inventory(page, launch_params)
    _filter_button(page).click()

    filters = page.get_by_role(
        "dialog",
        name="Фильтры предметов",
    )
    expect(filters).to_be_visible()
    filters.get_by_role("button", name=f"T{tier}", exact=True).click()
    filters.get_by_role(
        "button",
        name=f"Применить ({len(expected_item_ids)})",
    ).click()

    expect(filters).to_have_count(0)
    tier_chip = page.get_by_role(
        "button",
        name=f"Тир: {tier}",
    )
    expect(tier_chip).to_be_visible()
    _expect_filtered_items(page, inventory, expected_item_ids)

    tier_chip.click()

    expect(tier_chip).to_have_count(0)
    _expect_filtered_items(
        page,
        inventory,
        {item["id"] for item in inventory},
    )


@pytest.mark.regression
def test_combine_inventory_filters_and_reset_all(
    page: Page,
    playwright: Playwright,
) -> None:
    launch_params = get_required_env("VK_LAUNCH_PARAMS_USER_1")
    inventory = get_user_inventory(playwright, launch_params)
    expected_combination = {
        item["id"]
        for item in inventory
        if item["tier"] == 2 and item["rarity"] == "Common"
    }
    expected_common = {
        item["id"]
        for item in inventory
        if item["rarity"] == "Common"
    }

    assert expected_combination
    _open_inventory(page, launch_params)
    _filter_button(page).click()

    filters = page.get_by_role(
        "dialog",
        name="Фильтры предметов",
    )
    filters.get_by_role("button", name="T2", exact=True).click()
    filters.get_by_role("button", name="Обычный", exact=True).click()
    filters.get_by_role(
        "button",
        name=f"Применить ({len(expected_combination)})",
    ).click()

    _expect_filtered_items(
        page,
        inventory,
        expected_combination,
    )

    tier_chip = page.get_by_role("button", name="Тир: 2")
    rarity_chip = page.get_by_role(
        "button",
        name="Обычный",
        exact=True,
    )
    expect(tier_chip).to_be_visible()
    expect(rarity_chip).to_be_visible()

    tier_chip.click()

    expect(tier_chip).to_have_count(0)
    expect(rarity_chip).to_be_visible()
    _expect_filtered_items(page, inventory, expected_common)

    page.get_by_role(
        "button",
        name="Сбросить все",
    ).click()

    expect(rarity_chip).to_have_count(0)
    _expect_filtered_items(
        page,
        inventory,
        {item["id"] for item in inventory},
    )


@pytest.mark.regression
def test_inventory_tabs_show_matching_item_types(
    page: Page,
    playwright: Playwright,
) -> None:
    launch_params = get_required_env("VK_LAUNCH_PARAMS_USER_1")
    inventory = get_user_inventory(playwright, launch_params)
    expected_by_tab = {
        "Всё": {item["id"] for item in inventory},
        "Снаряжение": {
            item["id"]
            for item in inventory
            if item["type"] in EQUIPMENT_TYPES
        },
        "Ресурсы": {
            item["id"]
            for item in inventory
            if item["type"] == "Ресурс"
        },
        "Еда": {
            item["id"]
            for item in inventory
            if item["type"] in FOOD_TYPES
        },
    }

    _open_inventory(page, launch_params)

    for tab_name, expected_item_ids in expected_by_tab.items():
        page.get_by_role(
            "button",
            name=tab_name,
            exact=True,
        ).click()
        _expect_filtered_items(
            page,
            inventory,
            expected_item_ids,
        )


@pytest.mark.regression
def test_item_information_dialogs_and_close_behaviour(
    page: Page,
    playwright: Playwright,
) -> None:
    launch_params = get_required_env("VK_LAUNCH_PARAMS_USER_1")
    inventory = get_user_inventory(playwright, launch_params)
    item = next(
        inventory_item
        for inventory_item in inventory
        if inventory_item["id"] == DETAIL_ITEM_ID
    )

    _open_inventory(page, launch_params)
    item_dialog = _open_item_dialog(page, item["name"])

    expect(item_dialog).to_contain_text(f"T{item['tier']}")
    expect(item_dialog).to_contain_text("Обычный")
    expect(item_dialog).to_contain_text(
        re.compile(
            rf"Прочность\s*{item['durability']['current']}\s*/\s*"
            rf"{item['durability']['max']}"
        )
    )
    expect(item_dialog).to_contain_text(re.compile(r"1\s*Сумка"))

    item_dialog.get_by_role(
        "button",
        name=re.compile(r"110 Мощь"),
    ).click()
    ip_dialog = page.get_by_role("dialog").filter(
        has=page.get_by_role(
            "heading",
            name="Детализация Мощи Предмета (IP)",
        )
    )
    expect(ip_dialog).to_contain_text("110 IP")
    expect(ip_dialog).to_contain_text(
        re.compile(r"Базовая мощь 1 Тира:\s*\+100 IP")
    )
    expect(ip_dialog).to_contain_text(
        re.compile(
            r"Специализация предмета \(Ур\. 1\):\s*\+10 IP"
        )
    )
    ip_dialog.get_by_role(
        "button",
        name="Закрыть детализацию",
    ).click()
    expect(ip_dialog).to_have_count(0)

    item_dialog.get_by_role("button", name="Параметры").click()
    parameters_dialog = page.get_by_role("dialog").filter(
        has=page.get_by_role(
            "heading",
            name="Параметры и характеристики",
        )
    )
    expect(parameters_dialog).to_contain_text(
        re.compile(r"Мощь предмета \(IP\):\s*110 IP")
    )
    expect(parameters_dialog).to_contain_text(
        re.compile(r"Ячейка снаряжения:\s*Правая рука")
    )
    expect(parameters_dialog).to_contain_text(
        re.compile(r"Атака / Урон:\s*\+43")
    )
    expect(parameters_dialog).to_contain_text(
        re.compile(r"Скорость атаки:\s*1\.2/с")
    )
    parameters_dialog.get_by_role(
        "button",
        name="Закрыть параметры",
    ).click()
    expect(parameters_dialog).to_have_count(0)

    item_dialog.get_by_role("button", name="Навыки").click()
    skills_dialog = page.get_by_role("dialog").filter(
        has=page.get_by_role(
            "heading",
            name="Заклинания и навыки",
        )
    )
    for expected_skill in (
        "Удар рассечения",
        "Героический рывок",
        "Могучий раскол",
        "Глубокие раны",
    ):
        expect(skills_dialog).to_contain_text(expected_skill)
    skills_dialog.get_by_role(
        "button",
        name="Закрыть навыки",
    ).click()
    expect(skills_dialog).to_have_count(0)

    item_dialog.get_by_role("button", name="Закрыть", exact=True).click()
    expect(item_dialog).to_have_count(0)

    item_dialog = _open_item_dialog(page, item["name"])
    page.mouse.click(5, 100)
    expect(item_dialog).to_have_count(0)


@pytest.mark.regression
@pytest.mark.parametrize(
    "viewport",
    [
        pytest.param({"width": 1280, "height": 720}, id="desktop"),
        pytest.param({"width": 390, "height": 844}, id="vk-mini-app"),
    ],
)
def test_item_dialog_controls_fit_viewport(
    page: Page,
    viewport: dict[str, int],
) -> None:
    launch_params = get_required_env("VK_LAUNCH_PARAMS_USER_1")
    page.set_viewport_size(viewport)
    _open_inventory(page, launch_params)
    item_dialog = _open_item_dialog(page, "Ржавый Меч")

    controls = [
        item_dialog.get_by_role("button", name="Параметры"),
        item_dialog.get_by_role("button", name="Навыки"),
        item_dialog.get_by_role("button", name="Надеть"),
        item_dialog.get_by_role("button", name="На склад"),
        item_dialog.get_by_role("button", name="Разобрать"),
    ]

    expect(item_dialog).to_be_visible()
    expect(item_dialog).to_be_in_viewport()
    for control in controls:
        expect(control).to_be_visible()
        expect(control).to_be_in_viewport()
        control.click(trial=True)


@pytest.mark.regression
@pytest.mark.parametrize(
    "viewport",
    [
        pytest.param({"width": 1280, "height": 720}, id="desktop"),
        pytest.param({"width": 390, "height": 844}, id="vk-mini-app"),
    ],
)
def test_inventory_primary_controls_are_actionable_in_viewport(
    page: Page,
    viewport: dict[str, int],
) -> None:
    launch_params = get_required_env("VK_LAUNCH_PARAMS_USER_1")
    page.set_viewport_size(viewport)
    _open_inventory(page, launch_params)

    controls = [
        page.get_by_role("button", name="Сумка", exact=True).first,
        page.get_by_role(
            "button",
            name=re.compile(r"^Склад"),
        ),
        page.get_by_role("button", name="Всё", exact=True),
        page.get_by_role("button", name="Снаряжение", exact=True),
        page.get_by_role("button", name="Ресурсы", exact=True),
        page.get_by_role("button", name="Еда", exact=True),
        _filter_button(page),
    ]

    for control in controls:
        expect(control).to_be_visible()
        expect(control).to_be_in_viewport()
        control.click(trial=True)

    guild_storage = page.get_by_role(
        "button",
        name=re.compile(r"^Гильдия"),
    )
    expect(guild_storage).to_be_visible()
    expect(guild_storage).to_be_in_viewport()
    if guild_storage.is_enabled():
        guild_storage.click(trial=True)


@pytest.mark.regression
def test_helmet_visibility_control_has_switch_semantics(
    user_1_page: Page,
) -> None:
    launch_params = get_required_env("VK_LAUNCH_PARAMS_USER_1")
    user_1_page.goto(get_required_env("BASE_URL") + launch_params)
    user_1_page.get_by_role(
        "button",
        name="Инвентарь",
        exact=True,
    ).click()
    user_1_page.get_by_role(
        "button",
        name="Настройки внешности",
        exact=True,
    ).click()

    helmet_switch = user_1_page.get_by_role(
        "switch",
        name=re.compile(r"^Скрыть шлем"),
    )
    expect(helmet_switch).to_be_visible()
    initial_value = helmet_switch.get_attribute("aria-checked")
    assert initial_value in {"true", "false"}
    toggled_value = "false" if initial_value == "true" else "true"

    helmet_switch.click()
    expect(helmet_switch).to_have_attribute("aria-checked", toggled_value)

    helmet_switch.click()
    expect(helmet_switch).to_have_attribute("aria-checked", initial_value)


@pytest.mark.regression
def test_stomach_information_matches_profile(
    user_1_page: Page,
    playwright: Playwright,
) -> None:
    launch_params = get_required_env("VK_LAUNCH_PARAMS_USER_1")
    stomach = get_user_profile(playwright, launch_params)["stomach"]
    _open_inventory(user_1_page, launch_params)

    # UI-017: the summary button currently exposes only "T{level} ›".
    user_1_page.get_by_role(
        "button",
        name=f"T{stomach['level']} ›",
        exact=True,
    ).click()
    stomach_dialog = user_1_page.get_by_role("dialog", name="Желудок")

    expect(stomach_dialog).to_be_visible()
    expect(stomach_dialog).to_contain_text(f"Ранг T{stomach['level']}")
    expect(stomach_dialog).to_contain_text(
        f"Уровень {float(stomach['level']):.2f}"
    )
    expect(stomach_dialog).to_contain_text(
        re.compile(
            rf"{stomach['fullness']}\s*/\s*{stomach['maxFullness']}"
        )
    )

    stomach_dialog.get_by_role(
        "button",
        name="Закрыть",
        exact=True,
    ).click()
    expect(stomach_dialog).to_have_count(0)


@pytest.mark.regression
def test_character_power_updates_after_api_equipment_and_closes_on_backdrop(
    user_1_page: Page,
    playwright: Playwright,
) -> None:
    launch_params = get_required_env("VK_LAUNCH_PARAMS_USER_1")
    item = next(
        item
        for item in get_user_inventory(playwright, launch_params)
        if item["id"] == DETAIL_ITEM_ID
    )
    equipped = False

    try:
        _open_inventory(user_1_page, launch_params)
        item_dialog = _open_item_dialog(user_1_page, item["name"])
        power_control = item_dialog.get_by_role(
            "button",
            name=re.compile(r"^\d+ Мощь"),
        )
        item_power_match = re.search(r"\d+", power_control.inner_text())
        assert item_power_match is not None
        item_power = int(item_power_match.group())
        item_dialog.get_by_role(
            "button",
            name="Закрыть",
            exact=True,
        ).click()

        user_1_page.get_by_role(
            "button",
            name="0 ›",
            exact=True,
        ).click()
        power_dialog = user_1_page.get_by_role("dialog").filter(
            has=user_1_page.get_by_role(
                "heading",
                name="Мощь персонажа",
            )
        )
        expect(power_dialog).to_contain_text("0 IP")
        expect(power_dialog).to_contain_text("0 / 8 слотов")
        power_dialog.get_by_role(
            "button",
            name="Закрыть обзор",
            exact=True,
        ).click()

        equip_inventory_item(
            playwright,
            launch_params,
            item["id"],
            "mainHand",
        )
        equipped = True
        assert get_user_profile(playwright, launch_params)["equipment"][
            "mainHand"
        ]["id"] == item["id"]

        user_1_page.reload()
        expect(user_1_page.get_by_role("heading", name="Инвентарь")).to_be_visible()
        user_1_page.get_by_role(
            "button",
            name=f"{item_power} ›",
            exact=True,
        ).click()
        power_dialog = user_1_page.get_by_role("dialog").filter(
            has=user_1_page.get_by_role(
                "heading",
                name="Мощь персонажа",
            )
        )
        expect(power_dialog).to_contain_text(f"{item_power} IP")
        expect(power_dialog).to_contain_text("1 / 8 слотов")
        expect(power_dialog).to_contain_text(item["name"])
        expect(power_dialog).to_contain_text(f"+{item_power} IP")

        explanation = power_dialog.get_by_text(
            re.compile(r"^Мощь предметов \(IP\) повышает"),
        )
        explanation.scroll_into_view_if_needed()
        expect(explanation).to_be_visible()

        dialog_box = power_dialog.bounding_box()
        assert dialog_box is not None
        assert dialog_box["x"] > 0 or dialog_box["y"] > 0
        user_1_page.mouse.click(0, 0)
        expect(power_dialog).to_have_count(0)
    finally:
        if equipped:
            unequip_inventory_item(
                playwright,
                launch_params,
                "mainHand",
            )
