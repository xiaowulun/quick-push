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
