from bot.core.cache_stability import CACHE_TTLS, model_cache_settings


def test_anthropic_retains_cache_breakpoints():
    config = model_cache_settings("anthropic")
    assert config["anthropic_cache_tool_definitions"] == CACHE_TTLS["tool_definitions"]
    assert config["anthropic_cache_instructions"] == CACHE_TTLS["instructions"]
    assert config["anthropic_cache_messages"] == CACHE_TTLS["messages"]
    assert not any(key.startswith("openai_") for key in config)


def test_openai_uses_stable_role_key_without_anthropic_controls():
    config = model_cache_settings("openai")
    assert config["openai_prompt_cache_key"] == "phi:main"
    assert config == model_cache_settings("openai")
    assert not any(key.startswith("anthropic_") for key in config)
    assert "openai_prompt_cache_retention" not in config
