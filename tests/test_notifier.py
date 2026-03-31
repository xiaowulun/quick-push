import pytest
from utils.notifier import Notifier, TrendingMessage


class TestNotifier:
    def setup_method(self):
        self.notifier = Notifier(mode="print")

    def test_format_stars(self):
        assert self.notifier._format_stars(15000) == "1.5万"
        assert self.notifier._format_stars(2500) == "2.5k"
        assert self.notifier._format_stars(999) == "999"
        assert self.notifier._format_stars(10000) == "1.0万"

    def test_notifier_creation(self):
        notifier = Notifier(mode="feishu")
        assert notifier.mode == "feishu"


class TestTrendingMessage:
    def test_message_creation(self):
        msg = TrendingMessage(
            repo_name="owner/repo",
            description="A test repository",
            url="https://github.com/owner/repo",
            stars=1000,
            stars_today=50,
            language="Python",
            summary="Test summary",
            reasons=["reason1", "reason2"]
        )
        assert msg.repo_name == "owner/repo"
        assert msg.stars == 1000
        assert len(msg.reasons) == 2