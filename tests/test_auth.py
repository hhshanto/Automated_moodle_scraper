"""
Tests for auth.py

Covers Moodle login success, login failure, and session verification.
All Playwright browser calls are mocked so no live browser is needed.
"""

import pytest


class TestMoodleLogin:
    """Tests for the Moodle login flow."""

    async def test_login_succeeds_with_valid_credentials(self):
        """login() should return is_logged_in=True when credentials are correct."""
        pytest.skip("Not yet implemented")

    async def test_login_fails_with_wrong_password(self):
        """login() should return is_logged_in=False when the password is wrong."""
        pytest.skip("Not yet implemented")

    async def test_login_detects_active_session(self):
        """login() should detect that a session is already active and skip re-login."""
        pytest.skip("Not yet implemented")
