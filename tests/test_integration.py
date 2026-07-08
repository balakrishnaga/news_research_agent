"""Integration smoke tests ensuring config loads and scraper wiring works."""

import os
import yaml
from unittest.mock import patch


def test_config_has_date_filter():
    with open("config.yaml") as f:
        config = yaml.safe_load(f)
    assert "date_filter" in config
    assert "enabled" in config["date_filter"]


def test_config_has_image_search():
    with open("config.yaml") as f:
        config = yaml.safe_load(f)
    assert "image_search" in config
    assert "enabled" in config["image_search"]
    assert config["image_search"]["provider"] == "google_cse"


def test_scraper_date_filter_with_no_articles():
    from scraper.engine import NewsScraper
    scraper = NewsScraper()
    result = scraper.filter_current_date([])
    assert result == []


def test_scraper_date_filter_keeps_today():
    from datetime import datetime
    from zoneinfo import ZoneInfo
    from scraper.engine import NewsScraper

    today = datetime.now(ZoneInfo("Asia/Kolkata")).date()
    articles = [
        {"title": "Today", "article_date": today},
        {"title": "No date"},
    ]
    scraper = NewsScraper()
    result = scraper.filter_current_date(articles)
    assert len(result) == 1
    assert result[0]["title"] == "Today"


def test_google_searcher_initializes():
    from scraper.images import GoogleImageSearcher
    searcher = GoogleImageSearcher("test", "test", {"google_cse": {}})
    assert searcher.api_key == "test"
    assert searcher.cse_id == "test"
    assert searcher.target_width == 1200
    assert searcher.target_height == 600


def test_google_searcher_build_query():
    from scraper.images import GoogleImageSearcher
    searcher = GoogleImageSearcher("k", "c", {})
    query = searcher.build_query(["NTR", "Devara"], "NTR's Devara Storms Box Office")
    assert "NTR" in query
    assert "Devara" in query
    assert "telugu cinema" in query


def test_nodes_imports():
    # Verify graph nodes can import without errors
    import graph.nodes as nodes
    assert callable(nodes.scrape_news)
    assert callable(nodes.verify_facts)
