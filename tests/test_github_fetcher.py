import pytest
import asyncio
from unittest.mock import patch, MagicMock
from core.github_fetcher import GitHubFetcher, Repo


@pytest.fixture
def mock_config():
    config = MagicMock()
    config.github.max_retries = 1
    config.github.timeout = 5
    config.github.api_base = "https://api.github.com"
    config.github.token = ""
    return config


class TestGitHubFetcher:
    def setup_method(self):
        pass

    def test_parse_number(self, mock_config):
        with patch("core.github_fetcher.get_config", return_value=mock_config):
            fetcher = GitHubFetcher()
            assert fetcher._parse_number("1.5k") == 1500
            assert fetcher._parse_number("2.3M") == 2300000
            assert fetcher._parse_number("12345") == 12345
            assert fetcher._parse_number("1,234") == 1234

    def test_fetch_trending_with_invalid_language(self, mock_config):
        with patch("core.github_fetcher.get_config", return_value=mock_config):
            fetcher = GitHubFetcher()
            repos = fetcher.fetch_trending(language="invalid_language_xyz", limit=5)
            assert isinstance(repos, list)


class TestRepo:
    def test_repo_creation(self):
        repo = Repo(
            name="test-repo",
            full_name="owner/test-repo",
            description="Test description",
            url="https://github.com/owner/test-repo",
            stars=1000,
            language="Python",
            forks=100,
            stars_today=50,
            readme="# Test"
        )
        assert repo.name == "test-repo"
        assert repo.full_name == "owner/test-repo"
        assert repo.stars == 1000
        assert repo.readme == "# Test"


class TestAsyncFunctions:
    def test_semaphore_creation(self):
        semaphore = asyncio.Semaphore(5)
        assert semaphore._value == 5

    @pytest.mark.asyncio
    async def test_async_sleep(self):
        await asyncio.sleep(0.01)
        assert True