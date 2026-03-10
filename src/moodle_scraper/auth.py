"""
auth.py

Handles Moodle authentication for two login flows:
  - "sso": DFN-AAI Shibboleth SSO (default, for the University of Potsdam Moodle).
  - "standard": Direct Moodle username/password form (for open/test Moodle instances).

Set MOODLE_AUTH_TYPE=standard in .env to use the direct login flow.
All browser primitives (launch, navigate, screenshot, close) live in browser.py.
This module only knows about authentication logic.
"""

import logging
import os

from moodle_scraper.browser import active_session

logger = logging.getLogger(__name__)

# CSS selectors for verifying Moodle login success.
LOGIN_SUCCESS_SELECTOR = ".usermenu"

# CSS selectors for the DFN-AAI SSO organization picker page (WAYF).
SSO_ORGANISATION_SELECT_SELECTOR = "#userIdPSelection"
SSO_ORGANISATION_SUBMIT_SELECTOR = "input[name='Select']"
SSO_ORGANISATION_VALUE = "https://idp.uni-potsdam.de/idp/shibboleth"

# CSS selectors for the University of Potsdam SSO login form.
SSO_USERNAME_SELECTOR = "#username"
SSO_PASSWORD_SELECTOR = "#password"
SSO_LOGIN_BUTTON_SELECTOR = "button[type='submit']"

# CSS selectors for the standard Moodle login form (no SSO).
STANDARD_USERNAME_SELECTOR = "#username"
STANDARD_PASSWORD_SELECTOR = "#password"
STANDARD_LOGIN_BUTTON_SELECTOR = "#loginbtn"


async def login_to_moodle(username: str, password: str, base_url: str) -> bool:
    """
    Log into Moodle using the appropriate login flow.

    The login flow is controlled by the MOODLE_AUTH_TYPE environment variable:
      - "sso" (default): DFN-AAI Shibboleth SSO for the University of Potsdam.
      - "standard": Direct Moodle username/password form (for open/test instances).

    Args:
        username: The Moodle or SSO username.
        password: The Moodle or SSO password.
        base_url: The base URL of the Moodle instance.

    Returns:
        True if login succeeded, False if the credentials were rejected.
    """
    if active_session.page is None:
        raise RuntimeError("Browser is not running. Call launch_browser() first.")

    auth_type = os.getenv("MOODLE_AUTH_TYPE", "sso").strip().lower()
    login_url = base_url.rstrip("/") + "/login/index.php"

    try:
        await active_session.page.goto(login_url, wait_until="domcontentloaded")
        logger.info("Navigated to login page: %s (auth_type=%s)", login_url, auth_type)

        if auth_type == "standard":
            await _fill_standard_moodle_login_form(username, password)
        else:
            # Default: DFN-AAI SSO flow.
            await _handle_sso_organisation_picker()
            await _fill_sso_login_form(username, password)
            await active_session.page.wait_for_url(f"{base_url}/**", timeout=30000)
            logger.info("Redirected back to Moodle after SSO login.")

        # Verify login was successful by checking for the user menu.
        try:
            await active_session.page.wait_for_selector(LOGIN_SUCCESS_SELECTOR, timeout=10000)
        except Exception:
            logger.error("Login failed -- did not find user menu after login.")
            active_session.is_logged_in = False
            return False

        await active_session.page.wait_for_load_state("networkidle")
        active_session.is_logged_in = True
        logger.info("Login succeeded for user: %s", username)
        return True

    except Exception as error:
        logger.error("Login attempt failed with an exception: %s", error)
        active_session.is_logged_in = False
        return False


async def _fill_standard_moodle_login_form(username: str, password: str) -> None:
    """
    Fill in the standard Moodle login form (no SSO) and submit.

    Used for open or test Moodle instances that have a native username/password
    form at /login/index.php instead of redirecting to an SSO provider.

    Args:
        username: The Moodle username.
        password: The Moodle password.
    """
    page = active_session.page

    await page.wait_for_selector(STANDARD_USERNAME_SELECTOR, timeout=10000)
    logger.info("Standard Moodle login form loaded.")

    await page.fill(STANDARD_USERNAME_SELECTOR, username)
    await page.fill(STANDARD_PASSWORD_SELECTOR, password)
    logger.info("Filled standard login credentials for user: %s", username)

    await page.click(STANDARD_LOGIN_BUTTON_SELECTOR)
    await page.wait_for_load_state("networkidle")
    logger.info("Submitted standard Moodle login form.")


async def _handle_sso_organisation_picker() -> None:
    """
    On the DFN-AAI WAYF page, select University of Potsdam and submit.

    The WAYF page uses a hidden <select> behind a custom autocomplete widget,
    so we set the value directly via JavaScript before clicking Submit.
    """
    page = active_session.page

    await page.wait_for_selector(SSO_ORGANISATION_SELECT_SELECTOR, state="attached", timeout=10000)
    logger.info("DFN-AAI organisation picker detected.")

    await page.evaluate(
        """(value) => {
            const select = document.querySelector('#userIdPSelection');
            select.value = value;
            select.dispatchEvent(new Event('change'));
        }""",
        SSO_ORGANISATION_VALUE,
    )
    logger.info("Selected organisation via JS: %s", SSO_ORGANISATION_VALUE)

    await page.click(SSO_ORGANISATION_SUBMIT_SELECTOR)
    await page.wait_for_load_state("networkidle")
    logger.info("Submitted organisation selection.")


async def _fill_sso_login_form(username: str, password: str) -> None:
    """
    Fill in the university SSO login form with credentials and submit.

    Args:
        username: The SSO username.
        password: The SSO password.
    """
    page = active_session.page

    await page.wait_for_selector(SSO_USERNAME_SELECTOR, timeout=10000)
    logger.info("SSO login form loaded.")

    await page.fill(SSO_USERNAME_SELECTOR, username)
    await page.fill(SSO_PASSWORD_SELECTOR, password)
    logger.info("Filled SSO credentials for user: %s", username)

    await page.click(SSO_LOGIN_BUTTON_SELECTOR)
    logger.info("Submitted SSO login form.")
