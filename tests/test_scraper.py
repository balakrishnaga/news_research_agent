import pytest
from datetime import date, timedelta, datetime
from zoneinfo import ZoneInfo

from scraper.engine import NewsScraper


def test_extract_date_meta_tag():
    html = '''<html><head>
        <meta property="article:published_time" content="2026-06-21T08:30:00+05:30">
    </head></html>'''
    scraper = NewsScraper()
    result = scraper.extract_date(html, "123telugu")
    assert result == date(2026, 6, 21)


def test_extract_date_time_tag():
    html = '<html><time datetime="2026-06-21T10:00:00Z"></time></html>'
    scraper = NewsScraper()
    result = scraper.extract_date(html, "gulte")
    assert result == date(2026, 6, 21)


def test_extract_date_human_readable():
    html = '<html><body><span class="date">21 June 2026</span></body></html>'
    scraper = NewsScraper()
    result = scraper.extract_date(html, "telugu360")
    assert result == date(2026, 6, 21)


def test_extract_date_not_found():
    html = "<html><body>No date here</body></html>"
    scraper = NewsScraper()
    result = scraper.extract_date(html, "123telugu")
    assert result is None


def test_filter_current_date_keeps_today():
    today = datetime.now(ZoneInfo("Asia/Kolkata")).date()
    articles = [
        {"title": "Today", "url": "http://example.com/1", "article_date": today},
        {"title": "Yesterday", "url": "http://example.com/2", "article_date": None},
    ]
    scraper = NewsScraper()
    result = scraper.filter_current_date(articles)
    assert len(result) == 1
    assert result[0]["title"] == "Today"


def test_filter_current_date_excludes_old():
    today = datetime.now(ZoneInfo("Asia/Kolkata")).date()
    yesterday = today - timedelta(days=1)
    articles = [
        {"title": "Today", "url": "http://example.com/1", "article_date": today},
        {"title": "Yesterday", "url": "http://example.com/2", "article_date": yesterday},
    ]
    scraper = NewsScraper()
    result = scraper.filter_current_date(articles)
    assert len(result) == 1
    assert result[0]["title"] == "Today"


def test_filter_current_date_respects_fallback_days():
    today = datetime.now(ZoneInfo("Asia/Kolkata")).date()
    yesterday = today - timedelta(days=1)
    two_days_ago = today - timedelta(days=2)
    articles = [
        {"title": "Today", "article_date": today},
        {"title": "Yesterday", "article_date": yesterday},
        {"title": "Old", "article_date": two_days_ago},
    ]
    scraper = NewsScraper()
    result = scraper.filter_current_date(articles, fallback_days=1)
    assert len(result) == 2
    assert result[0]["title"] == "Today"
    assert result[1]["title"] == "Yesterday"
