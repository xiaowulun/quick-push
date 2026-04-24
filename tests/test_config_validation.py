import pytest

from app.infrastructure import config as config_module


@pytest.fixture(autouse=True)
def _reset_config():
    config_module.reset_config()
    yield
    config_module.reset_config()


def test_missing_openai_key_raises(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)

    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        config_module.get_config()


def test_missing_github_token_is_allowed(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)

    cfg = config_module.get_config()
    assert cfg.github.token == ""


def test_openai_model_env_values_are_stripped(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_MODEL_EASY", "  Qwen/Qwen3-32B  ")
    monkeypatch.setenv("OPENAI_MODEL_MEDIUM", "  Pro/MiniMaxAI/MiniMax-M2.5")
    monkeypatch.setenv("OPENAI_MODEL_HARD", "Pro/deepseek-ai/DeepSeek-V3  ")

    cfg = config_module.get_config()
    assert cfg.openai.model_easy == "Qwen/Qwen3-32B"
    assert cfg.openai.model_medium == "Pro/MiniMaxAI/MiniMax-M2.5"
    assert cfg.openai.model_hard == "Pro/deepseek-ai/DeepSeek-V3"
    assert cfg.openai.model_chat == "Pro/MiniMaxAI/MiniMax-M2.5"
    assert cfg.openai.model_pro == "Pro/deepseek-ai/DeepSeek-V3"


def test_openai_model_env_falls_back_when_value_is_not_in_whitelist(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_MODEL_EASY", "foo-easy")
    monkeypatch.setenv("OPENAI_MODEL_MEDIUM", "foo-medium")
    monkeypatch.setenv("OPENAI_MODEL_HARD", "foo-hard")

    cfg = config_module.get_config()
    assert cfg.openai.model_easy == config_module.MODEL_EASY_DEFAULT
    assert cfg.openai.model_medium == config_module.MODEL_MEDIUM_DEFAULT
    assert cfg.openai.model_hard == config_module.MODEL_HARD_DEFAULT


def test_openai_legacy_model_env_is_still_supported(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.delenv("OPENAI_MODEL_EASY", raising=False)
    monkeypatch.delenv("OPENAI_MODEL_MEDIUM", raising=False)
    monkeypatch.delenv("OPENAI_MODEL_HARD", raising=False)
    monkeypatch.setenv("OPENAI_MODEL_FAST", "Qwen/Qwen3-32B")
    monkeypatch.setenv("OPENAI_MODEL_CHAT", "Pro/MiniMaxAI/MiniMax-M2.5")
    monkeypatch.setenv("OPENAI_MODEL_PRO", "Pro/deepseek-ai/DeepSeek-V3")

    cfg = config_module.get_config()
    assert cfg.openai.model_easy == "Qwen/Qwen3-32B"
    assert cfg.openai.model_medium == "Pro/MiniMaxAI/MiniMax-M2.5"
    assert cfg.openai.model_hard == "Pro/deepseek-ai/DeepSeek-V3"
