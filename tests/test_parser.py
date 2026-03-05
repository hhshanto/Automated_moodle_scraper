"""
Tests for parser.py

Covers HTML-based and vision-based LLM parsing. All Azure OpenAI API calls are mocked
so no real API key or cost is needed to run tests.
"""

import pytest


class TestHtmlParser:
    """Tests for the HTML-based LLM parsing path."""

    async def test_parse_multiple_choice_question_from_html(self):
        """parse_question_html() should correctly identify the correct answer in a multiple choice block."""
        pytest.skip("Not yet implemented")

    async def test_parse_question_with_general_feedback(self):
        """parse_question_html() should extract general feedback text when present."""
        pytest.skip("Not yet implemented")


class TestVisionParser:
    """Tests for the screenshot-based vision parsing path."""

    async def test_parse_question_from_screenshot(self):
        """parse_question_screenshot() should return a QuizQuestion object from a mock image response."""
        pytest.skip("Not yet implemented")

    async def test_parse_returns_error_on_api_failure(self):
        """parse_question_screenshot() should return an error dict when the API call fails."""
        pytest.skip("Not yet implemented")
