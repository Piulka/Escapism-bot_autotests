from collections.abc import Generator

import pytest
from dotenv import load_dotenv
from playwright.sync_api import Browser, Page, Playwright

from api_client import get_required_env, reset_user


load_dotenv()


@pytest.fixture
def reset_user_1(playwright: Playwright) -> None:
    reset_user(
        playwright,
        get_required_env("VK_LAUNCH_PARAMS_USER_1"),
    )


@pytest.fixture
def reset_user_2(playwright: Playwright) -> None:
    reset_user(
        playwright,
        get_required_env("VK_LAUNCH_PARAMS_USER_2"),
    )


@pytest.fixture
def user_1_page(
    browser: Browser,
    reset_user_1: None,
) -> Generator[Page, None, None]:
    context = browser.new_context()
    page = context.new_page()

    try:
        yield page
    finally:
        context.close()
