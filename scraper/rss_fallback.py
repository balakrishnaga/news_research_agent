"""RSS-based fallback for Telugu movie news when direct scraping fails."""

import logging
import urllib.parse
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional

import requests

logger = logging.getLogger(__name__)


def fetch_google_news_rss(query: str = "Telugu movie news", max_results: int = 10) -> List[Dict]:
    """
    Fetch news articles via Google News RSS feed.
    No API key required.
    """
    encoded_query = urllib.parse.quote(query)
    rss_url = (
        f"https://news.google.com/rss/search?q={encoded_query}"
        f"&hl=en-IN&gl=IN&ceid=IN:en"
    )

    try:
        logger.info("Fetching Google News RSS: %s", rss_url)
        resp = requests.get(rss_url, timeout=15, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        })
        resp.raise_for_status()
        return _parse_rss(resp.text, max_results)
    except requests.RequestException as exc:
        logger.warning("Google News RSS failed: %s", exc)
        return []


def _parse_rss(xml_text: str, max_results: int) -> List[Dict]:
    """Parse Google News RSS XML into article dicts."""
    articles = []
    try:
        root = ET.fromstring(xml_text)
        # Find channel/items (works for standard RSS 2.0 + Google News)
        channel = root.find("channel")
        if channel is None:
            return articles

        items = channel.findall("item")[:max_results]
        for item in items:
            title = item.findtext("title", default="").strip()
            link = item.findtext("link", default="").strip()
            description = item.findtext("description", default="").strip()
            pub_date = item.findtext("pubDate", default="").strip()

            if not title or not link:
                continue

            # Remove source suffix Google adds (e.g., " - Times of India")
            if " - " in title:
                title = title.rsplit(" - ", 1)[0].strip()

            articles.append({
                "source": "google_news_rss",
                "title": title,
                "url": link,
                "summary": description,
                "content": "",
                "published": pub_date,
            })
    except ET.ParseError as exc:
        logger.warning("RSS parse error: %s", exc)

    logger.info("RSS fallback yielded %d articles", len(articles))
    return articles


def fallback_articles(existing_articles: List[Dict], max_results: int = 10) -> List[Dict]:
    """
    Return existing articles if present; otherwise fetch from RSS fallback.
    """
    if existing_articles:
        return existing_articles

    logger.info("No articles from direct scraping. Trying RSS fallback...")
    rss_articles = fetch_google_news_rss(max_results=max_results)

    # Try to fetch full content for each RSS article
    from scraper.engine import NewsScraper
    scraper = NewsScraper(timeout=15)
    for art in rss_articles:
        if art.get("url"):
            try:
                full = scraper.fetch_article_content(art["url"])
                art["content"] = full
            except Exception as exc:
                logger.debug("Could not fetch content for %s: %s", art["url"], exc)
                art["content"] = art.get("summary", "")

    return rss_articles
