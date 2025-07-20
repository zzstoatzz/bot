"""Pytest configuration"""

import pytest
from unittest.mock import Mock
from bot.core.atproto_client import BotClient


@pytest.fixture
def mock_client():
    """Mock AT Protocol client"""
    client = Mock(spec=BotClient)
    client.is_authenticated = True
    return client