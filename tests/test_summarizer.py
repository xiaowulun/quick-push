import pytest
from unittest.mock import patch, MagicMock
from core.summarizer import Summarizer


@pytest.fixture
def mock_config():
    config = MagicMock()
    config.behavior.max_retries = 1
    config.openai.api_key = "test-key"
    config.openai.base_url = "https://test.com"
    config.openai.model = "test-model"
    return config


class TestSummarizer:
    def setup_method(self):
        pass

    def test_summarize_without_readme(self, mock_config):
        with patch("core.summarizer.get_config", return_value=mock_config):
            summarizer = Summarizer()
            result = summarizer.summarize(
                repo_name="test/repo",
                description="A test repo",
                readme_content=None,
                stars=100
            )
            assert result["summary"] == "该项目没有README文件"
            assert "无法分析" in result["reasons"][0]

    def test_summarize_with_empty_readme(self, mock_config):
        with patch("core.summarizer.get_config", return_value=mock_config):
            summarizer = Summarizer()
            result = summarizer.summarize(
                repo_name="test/repo",
                description="A test repo",
                readme_content="",
                stars=100
            )
            assert result["summary"] == "该项目没有README文件"