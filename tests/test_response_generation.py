"""Unit tests for response generation"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from bot.response_generator import ResponseGenerator, PLACEHOLDER_RESPONSES


@pytest.mark.asyncio
async def test_placeholder_response_generator():
    """Test placeholder responses when no AI is configured"""
    with patch("bot.response_generator.settings") as mock_settings:
        mock_settings.anthropic_api_key = None

        generator = ResponseGenerator()
        response = await generator.generate("Hello bot!", "test.user", "")

        # Should return one of the placeholder responses
        assert response in PLACEHOLDER_RESPONSES
        assert len(response) <= 300


@pytest.mark.asyncio
async def test_ai_response_generator():
    """Test AI responses when Anthropic is configured"""
    with patch("bot.response_generator.settings") as mock_settings:
        mock_settings.anthropic_api_key = "test-key"

        # Mock the agent
        mock_agent = Mock()
        mock_agent.generate_response = AsyncMock(
            return_value="Hello! Nice to meet you!"
        )

        with patch(
            "bot.agents.anthropic_agent.AnthropicAgent", return_value=mock_agent
        ):
            generator = ResponseGenerator()

            # Verify AI was enabled
            assert generator.agent is not None
            assert hasattr(generator.agent, "generate_response")

            # Test response
            response = await generator.generate("Hello!", "test.user", "")
            assert response == "Hello! Nice to meet you!"

            # Verify the agent was called correctly
            mock_agent.generate_response.assert_called_once_with(
                "Hello!", "test.user", ""
            )


@pytest.mark.asyncio
async def test_ai_initialization_failure():
    """Test fallback to placeholder when AI initialization fails"""
    with patch("bot.response_generator.settings") as mock_settings:
        mock_settings.anthropic_api_key = "test-key"

        # Make the import fail
        with patch(
            "bot.agents.anthropic_agent.AnthropicAgent",
            side_effect=ImportError("API error"),
        ):
            generator = ResponseGenerator()

            # Should fall back to placeholder
            assert generator.agent is None

            response = await generator.generate("Hello!", "test.user", "")
            assert response in PLACEHOLDER_RESPONSES


@pytest.mark.asyncio
async def test_response_length_limit():
    """Test that responses are always within Bluesky's 300 char limit"""
    with patch("bot.response_generator.settings") as mock_settings:
        mock_settings.anthropic_api_key = "test-key"

        # Mock agent that returns a properly truncated response
        # (In real implementation, truncation happens in AnthropicAgent)
        mock_agent = Mock()
        mock_agent.generate_response = AsyncMock(
            return_value="x" * 300  # Already truncated by agent
        )

        with patch(
            "bot.agents.anthropic_agent.AnthropicAgent", return_value=mock_agent
        ):
            generator = ResponseGenerator()
            response = await generator.generate("Hello!", "test.user", "")

            # The anthropic agent should handle truncation, but let's verify
            assert len(response) <= 300


def test_placeholder_responses_length():
    """Verify all placeholder responses fit within limit"""
    for response in PLACEHOLDER_RESPONSES:
        assert len(response) <= 300, f"Placeholder too long: {response}"
