from app.github.fetcher import GitHubFetcher


def test_parse_trending_stars_gain_daily():
    text = "1,234 stars today"
    assert GitHubFetcher._parse_trending_stars_gain(text) == 1234


def test_parse_trending_stars_gain_weekly():
    text = "2.5k stars this week"
    assert GitHubFetcher._parse_trending_stars_gain(text) == 2500


def test_parse_trending_stars_gain_monthly():
    text = "12,345 stars this month"
    assert GitHubFetcher._parse_trending_stars_gain(text) == 12345


def test_parse_trending_stars_gain_non_period_text_returns_zero():
    text = "10 forks"
    assert GitHubFetcher._parse_trending_stars_gain(text) == 0
