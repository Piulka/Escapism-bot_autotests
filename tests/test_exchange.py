from math import ceil, floor
import re
from urllib.parse import urlsplit

import pytest
from playwright.sync_api import Locator, Page, Playwright, Response, expect

from api_client import (
    get_exchange_pool,
    get_required_env,
    get_user_profile,
)


GOLD_TO_EXCHANGE = 200
FEE_RATE = 0.05
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
    fee = ceil(amount_in * FEE_RATE)
    amount_after_fee = amount_in - fee
    return (
        reserve_out * amount_after_fee
        // (reserve_in + amount_after_fee)
    )


def _calculate_gold_to_silver_rate(pool: dict[str, int]) -> int:
    return round(pool["silverReserve"] / pool["goldReserve"])


def _calculate_gold_to_silver_impact(
    pool: dict[str, int],
    amount_in: int,
    amount_out: int,
) -> float:
    current_rate = pool["silverReserve"] / pool["goldReserve"]
    fee = ceil(amount_in * FEE_RATE)
    amount_after_fee = amount_in - fee
    projected_gold = (
        pool["goldReserve"]
        + amount_after_fee
        + fee // 2
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


def _open_exchange(page: Page, launch_params: str) -> Locator:
    page.goto(get_required_env("BASE_URL") + launch_params)
    page.get_by_label("Биржа").click()
    amount_input = page.get_by_label("Сумма обмена")
    expect(amount_input).to_be_visible()
    return amount_input


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

    amount_input = _open_exchange(user_1_page, launch_params)
    _expect_displayed_rate(user_1_page, rate_before)

    user_1_page.get_by_role(
        "button",
        name="Обменять серебро на золото",
    ).click()
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
            exact=True,
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

    user_1_page.get_by_role(
        "button",
        name="Обменять золото на серебро",
    ).click()
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
            exact=True,
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

    _open_exchange(user_1_page, launch_params)
    expect(
        user_1_page.get_by_role(
            "heading",
            name="Биржа валюты",
        )
    ).to_be_visible()

    user_1_page.get_by_role(
        "button",
        name="О Бирже валюты",
    ).click()
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

    information_dialog.get_by_role(
        "button",
        name="Закрыть",
        exact=True,
    ).click()
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


@pytest.mark.regression
@pytest.mark.parametrize(
    ("invalid_value", "expected_input_value"),
    [
        pytest.param("", "", id="empty"),
        pytest.param("0", "0", id="zero"),
        pytest.param("99", "99", id="below-contract-minimum"),
        pytest.param("-1", "0", id="negative"),
        pytest.param("1.5", "1.5", id="fractional"),
        pytest.param("abc", "", id="non-numeric"),
    ],
)
def test_exchange_rejects_invalid_amounts(
    page: Page,
    invalid_value: str,
    expected_input_value: str,
) -> None:
    launch_params = get_required_env("VK_LAUNCH_PARAMS_USER_1")
    amount_input = _open_exchange(page, launch_params)

    if invalid_value == "abc":
        amount_input.press_sequentially(invalid_value)
    else:
        amount_input.fill(invalid_value)

    expect(amount_input).to_have_value(expected_input_value)
    expect(
        page.get_by_role(
            "button",
            name="Обменять",
            exact=True,
        )
    ).to_be_disabled()


@pytest.mark.regression
def test_exchange_allows_available_balance_and_rejects_excess(
    page: Page,
    playwright: Playwright,
) -> None:
    launch_params = get_required_env("VK_LAUNCH_PARAMS_USER_1")
    silver_balance = get_user_profile(
        playwright,
        launch_params,
    )["currencies"]["quants"]
    amount_input = _open_exchange(page, launch_params)
    submit = page.get_by_role(
        "button",
        name="Обменять",
        exact=True,
    )

    assert 0 < silver_balance <= 1_000_000

    amount_input.fill(str(silver_balance))
    expect(submit).to_be_enabled()

    amount_input.fill(str(silver_balance + 1))
    expect(submit).to_be_disabled()


@pytest.mark.regression
def test_exchange_double_submit_creates_only_one_transaction(
    user_1_page: Page,
    playwright: Playwright,
) -> None:
    launch_params = get_required_env("VK_LAUNCH_PARAMS_USER_1")
    profile_before = get_user_profile(playwright, launch_params)
    pool_before = get_exchange_pool(playwright, launch_params)
    silver_before = profile_before["currencies"]["quants"]
    gold_before = profile_before["currencies"]["fragments"]
    expected_silver = _calculate_amount_out(
        reserve_in=pool_before["goldReserve"],
        reserve_out=pool_before["silverReserve"],
        amount_in=GOLD_TO_EXCHANGE,
    )
    exchange_requests = []

    assert gold_before >= GOLD_TO_EXCHANGE
    amount_input = _open_exchange(user_1_page, launch_params)
    user_1_page.get_by_role(
        "button",
        name="Обменять серебро на золото",
    ).click()
    amount_input.fill(str(GOLD_TO_EXCHANGE))
    user_1_page.on(
        "request",
        lambda request: exchange_requests.append(request)
        if request.method == "POST"
        and urlsplit(request.url).path == "/api/exchange"
        else None,
    )

    profile_after_submit = None
    first_response = None
    submit_request_count = None
    try:
        with user_1_page.expect_response(
            _is_exchange_response,
        ) as exchange_info:
            user_1_page.get_by_role(
                "button",
                name="Обменять",
                exact=True,
            ).dblclick()

        first_response = exchange_info.value
        user_1_page.wait_for_timeout(500)
        profile_after_submit = get_user_profile(
            playwright,
            launch_params,
        )
        submit_request_count = len(exchange_requests)
    finally:
        profile_before_cleanup = get_user_profile(
            playwright,
            launch_params,
        )
        silver_to_return = (
            profile_before_cleanup["currencies"]["quants"]
            - silver_before
        )
        if silver_to_return > 0:
            amount_input = _open_exchange(user_1_page, launch_params)
            amount_input.fill(str(silver_to_return))
            with user_1_page.expect_response(
                _is_exchange_response,
            ) as cleanup_info:
                user_1_page.get_by_role(
                    "button",
                    name="Обменять",
                    exact=True,
                ).click()
            cleanup_response = cleanup_info.value
            assert cleanup_response.status == 200, (
                f"Exchange cleanup failed: {cleanup_response.text()}"
            )

    assert first_response is not None
    assert profile_after_submit is not None
    assert submit_request_count is not None
    assert first_response.status == 200, (
        f"Exchange failed: {first_response.text()}"
    )
    assert submit_request_count == 1, (
        "Double click sent more than one exchange request: "
        f"{submit_request_count}"
    )
    assert profile_after_submit["currencies"] == {
        "quants": silver_before + expected_silver,
        "fragments": gold_before - GOLD_TO_EXCHANGE,
    }


@pytest.mark.regression
@pytest.mark.parametrize(
    "viewport",
    [
        pytest.param({"width": 1280, "height": 720}, id="desktop"),
        pytest.param({"width": 390, "height": 844}, id="vk-mini-app"),
    ],
)
def test_exchange_primary_controls_fit_viewport(
    page: Page,
    viewport: dict[str, int],
) -> None:
    launch_params = get_required_env("VK_LAUNCH_PARAMS_USER_1")
    page.set_viewport_size(viewport)
    amount_input = _open_exchange(page, launch_params)

    controls = [
        page.get_by_role("button", name="О Бирже валюты"),
        amount_input,
        page.get_by_role("button", name="МАКС", exact=True),
        page.get_by_role("button", name=re.compile(r"^Увеличить на \d+$")),
        page.get_by_role("button", name=re.compile(r"^Уменьшить на \d+$")),
        page.get_by_role(
            "button",
            name="Обменять серебро на золото",
        ),
        page.get_by_role(
            "group",
            name="Допуск проскальзывания",
        ),
        page.get_by_role("button", name="Назад", exact=True),
        page.get_by_role("button", name="Обменять", exact=True),
    ]

    for control in controls:
        expect(control).to_be_visible()
        expect(control).to_be_in_viewport()

    for control in controls[:6]:
        if control.is_enabled():
            control.click(trial=True)


@pytest.mark.regression
def test_exchange_rejects_amount_above_contract_limit(page: Page) -> None:
    launch_params = get_required_env("VK_LAUNCH_PARAMS_USER_1")
    amount_input = _open_exchange(page, launch_params)

    amount_input.fill("2000000")

    expect(
        page.get_by_text(
            "Максимальная сумма обмена — 1 000 000",
            exact=True,
        )
    ).to_be_visible()
    expect(
        page.get_by_role("button", name="Обменять", exact=True)
    ).to_be_disabled()
