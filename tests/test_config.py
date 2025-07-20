"""Test configuration loading"""

from bot.config import settings


def test_config_loads():
    """Test that config loads without errors"""
    assert settings.bluesky_service == "https://bsky.social"
    assert settings.bot_name == "phi"
    assert settings.notification_poll_interval == 10
