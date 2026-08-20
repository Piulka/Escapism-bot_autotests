import os

import pytest
from dotenv import load_dotenv
from playwright.sync_api import Browser, Playwright


load_dotenv()


def reset_user(playwright: Playwright, launch_params: str):
    api_url = os.getenv("API_URL")

    api_context = playwright.request.new_context(
        base_url=api_url,
        extra_http_headers={
            "X-VK-Launch-Params": launch_params
        }
    )

    response = api_context.post("v1/account/reset")

    assert response.status == 200, (
        f"Failed to reset user. Status: {response.status}"
    )

    api_context.dispose()


def get_user_profile(playwright: Playwright, launch_params: str):
    api_url = os.getenv("API_URL")

    api_context = playwright.request.new_context(
        base_url=api_url,
        extra_http_headers={
            "X-VK-Launch-Params": launch_params
        }
    )

    response = api_context.get("v1/profile")

    assert response.status == 200, (
        f"Failed to get user profile. Status: {response.status}"
    )

    profile = response.json()

    api_context.dispose()

    return profile


@pytest.fixture
def reset_user_1(playwright: Playwright):
    reset_user(
        playwright,
        os.getenv("VK_LAUNCH_PARAMS_USER_1")
    )


@pytest.fixture
def reset_user_2(playwright: Playwright):
    reset_user(
        playwright,
        os.getenv("VK_LAUNCH_PARAMS_USER_2")
    )


@pytest.fixture
def user_1_page(
    browser: Browser,
    reset_user_1
):
    context = browser.new_context()
    page = context.new_page()

    yield page

    context.close()