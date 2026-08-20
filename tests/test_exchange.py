from math import floor
import re
from urllib.parse import urlsplit

import pytest
from playwright.sync_api import Page, Playwright, Response, expect

from api_client import (
    get_exchange_pool,
    get_required_env,
    get_user_profile,
)


GOLD_TO_EXCHANGE = 200
FEE_RATE = 0.05
REINVESTED_FEE_RATE = 0.5
SLIPPAGE_TOLERANCE = 0.01


def _is_exchange_response(response: Response) -> bool:
    return (
        response.request.method == "POST"
        and urlsplit(response.url).path == "/api/exchange"
    )


def _calculate_amount_out(
    reserve_in: int,
    reserve_out: int,
    amount_in: int,
) -> int:
    amount_after_fee = amount_in * (1 - FEE_RATE)
    return floor(
        reserve_out
        - reserve_in * reserve_out / (reserve_in + amount_after_fee)
    )


def _calculate_gold_to_silver_rate(pool: dict[str, int]) -> int:
    return round(pool["silverReserve"] / pool["goldReserve"])


def _calculate_gold_to_silver_impact(
    pool: dict[str, int],
    amount_in: int,
    amount_out: int,
) -> float:
    current_rate = pool["silverReserve"] / pool["goldReserve"]
    fee = amount_in * FEE_RATE
    projected_gold = (
        pool["goldReserve"]
        + amount_in
        - fee
        + fee * REINVESTED_FEE_RATE
    )
    projected_silver = pool["silverReserve"] - amount_out
    projected_rate = projected_silver / projected_gold

    return (current_rate - projected_rate) / current_rate * 100


def _expect_displayed_rate(page: Page, expected_rate: int) -> None:
    rate_panel = page.get_by_text(
        "Текущий курс",
        exact=True,
    ).locator("..")
    expect(rate_panel).to_contain_text(
        re.compile(rf"Текущий курс\s*1\s*=\s*{expected_rate}\b")
    )


@pytest.mark.smoke
def test_exchange_gold_to_silver_and_back(
    user_1_page: Page,
    playwright: Playwright,
) -> None:
    launch_params = get_required_env("VK_LAUNCH_PARAMS_USER_1")
    profile_before = get_user_profile(playwright, launch_params)
    pool_before = get_exchange_pool(playwright, launch_params)
    silver_before = profile_before["currencies"]["quants"]
    gold_before = profile_before["currencies"]["fragments"]
    rate_before = _calculate_gold_to_silver_rate(pool_before)

    assert gold_before >= GOLD_TO_EXCHANGE

    user_1_page.goto(get_required_env("BASE_URL") + launch_params)
    user_1_page.get_by_label("Биржа").click()

    amount_input = user_1_page.get_by_label("Сумма обмена")
    amount_input.wait_for()
    _expect_displayed_rate(user_1_page, rate_before)

    # TODO: ask frontend to add an aria-label to the direction button.
    direction_button = user_1_page.locator(
        "button:has(svg.lucide-arrow-down-up)"
    )
    direction_button.click()
    amount_input.fill(str(GOLD_TO_EXCHANGE))

    expected_silver = _calculate_amount_out(
        reserve_in=pool_before["goldReserve"],
        reserve_out=pool_before["silverReserve"],
        amount_in=GOLD_TO_EXCHANGE,
    )
    expected_impact = _calculate_gold_to_silver_impact(
        pool_before,
        GOLD_TO_EXCHANGE,
        expected_silver,
    )

    expect(
        user_1_page.get_by_text(
            f"+{expected_impact:.2f}%",
            exact=True,
        )
    ).to_be_visible()

    with user_1_page.expect_response(
        _is_exchange_response,
    ) as first_exchange_info:
        user_1_page.get_by_role(
            "button",
            name="Обменять",
        ).click()

    first_exchange = first_exchange_info.value
    first_exchange_data = first_exchange.json()

    assert first_exchange.status == 200, (
        f"Gold-to-silver exchange failed: {first_exchange.text()}"
    )
    assert first_exchange.request.post_data_json == {
        "from": "gold",
        "amountIn": GOLD_TO_EXCHANGE,
        "minAmountOut": floor(
            expected_silver * (1 - SLIPPAGE_TOLERANCE)
        ),
    }
    assert first_exchange_data["amountOut"] == expected_silver

    profile_after_first = get_user_profile(playwright, launch_params)
    pool_after_first = get_exchange_pool(playwright, launch_params)
    rate_after_first = _calculate_gold_to_silver_rate(pool_after_first)

    assert profile_after_first["currencies"] == {
        "quants": silver_before + expected_silver,
        "fragments": gold_before - GOLD_TO_EXCHANGE,
    }
    assert rate_after_first < rate_before
    _expect_displayed_rate(user_1_page, rate_after_first)

    direction_button.click()
    amount_input.fill(str(expected_silver))

    expected_gold = _calculate_amount_out(
        reserve_in=pool_after_first["silverReserve"],
        reserve_out=pool_after_first["goldReserve"],
        amount_in=expected_silver,
    )

    with user_1_page.expect_response(
        _is_exchange_response,
    ) as second_exchange_info:
        user_1_page.get_by_role(
            "button",
            name="Обменять",
        ).click()

    second_exchange = second_exchange_info.value
    second_exchange_data = second_exchange.json()

    assert second_exchange.status == 200, (
        f"Silver-to-gold exchange failed: {second_exchange.text()}"
    )
    assert second_exchange.request.post_data_json == {
        "from": "silver",
        "amountIn": expected_silver,
        "minAmountOut": floor(
            expected_gold * (1 - SLIPPAGE_TOLERANCE)
        ),
    }
    assert second_exchange_data["amountOut"] == expected_gold

    profile_after_second = get_user_profile(playwright, launch_params)
    pool_after_second = get_exchange_pool(playwright, launch_params)
    rate_after_second = _calculate_gold_to_silver_rate(pool_after_second)

    assert profile_after_second["currencies"] == {
        "quants": silver_before,
        "fragments": gold_before - GOLD_TO_EXCHANGE + expected_gold,
    }
    # The reverse exchange cannot restore the pool exactly: both operations
    # charge a fee and integer currency amounts are rounded down.
    assert abs(rate_after_second - rate_before) <= 1
    _expect_displayed_rate(user_1_page, rate_after_second)


@pytest.mark.regression
def test_exchange_information_and_back_navigation(
    user_1_page: Page,
) -> None:
    launch_params = get_required_env("VK_LAUNCH_PARAMS_USER_1")

    user_1_page.goto(get_required_env("BASE_URL") + launch_params)
    user_1_page.get_by_label("Биржа").click()
    expect(
        user_1_page.get_by_role(
            "heading",
            name="Биржа валюты",
        )
    ).to_be_visible()

    # TODO: replace icon locators when both controls receive accessible names.
    user_1_page.locator(
        "button:has(svg.lucide-info)"
    ).first.click()
    information_dialog = user_1_page.get_by_role(
        "dialog",
        name="О Бирже валюты",
    )
    expect(information_dialog).to_be_visible()
    expect(information_dialog).to_contain_text(
        "AMM (Automated Market Maker)"
    )
    expect(
        information_dialog.get_by_role(
            "heading",
            name="Как формируется цена?",
        )
    ).to_be_visible()
    expect(
        information_dialog.get_by_role(
            "heading",
            name="Комиссия и инфляция",
        )
    ).to_be_visible()
    expect(information_dialog).to_contain_text("комиссия 5%")

    information_dialog.get_by_role("button").click()
    expect(information_dialog).to_have_count(0)

    user_1_page.get_by_role(
        "button",
        name="Назад",
        exact=True,
    ).click()
    expect(
        user_1_page.get_by_role(
            "heading",
            name="Биржа валюты",
        )
    ).to_have_count(0)
    expect(user_1_page.get_by_label("Биржа")).to_be_visible()
