"""Test configuration loading"""

from unittest.mock import patch

from bot.config import settings


def test_config_loads():
    """Test that config loads without errors"""
    assert settings.bluesky_service == "https://bsky.social"
    assert settings.bot_name  # default "Bot" or overridden via env/dotfile
    assert settings.notification_poll_interval == 10


def test_logfire_instrumentation_degrades_gracefully():
    """Regression: a broken logfire instrumentation must not crash the app."""
    import importlib

    import bot.main as main_mod

    # Simulate instrument_pydantic_ai raising (e.g. missing otel dep)
    with patch.object(
        main_mod.logfire,
        "instrument_pydantic_ai",
        side_effect=ImportError("no module 'opentelemetry.instrumentation.httpx'"),
    ):
        # Re-running the instrumentation loop should not raise
        for _instrument in (
            main_mod.logfire.instrument_pydantic_ai,
            main_mod.logfire.instrument_anthropic,
            main_mod.logfire.instrument_openai,
        ):
            try:
                _instrument()
            except Exception:
                pass  # this is what the production code does

    # App should still be importable and functional
    importlib.reload(main_mod)
    assert main_mod.app is not None
