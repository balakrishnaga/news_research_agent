"""News source definitions for Telugu movie news."""

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class NewsSource:
    """Configuration for a single news source."""
    name: str
    url: str
    article_selector: str
    title_selector: str
    link_selector: str
    content_selector: str
    base_url: str
    enabled: bool = True
    rss_url: Optional[str] = None


# Curated list of Telugu cinema news sources.
# These are public websites with general movie news sections.
DEFAULT_SOURCES: List[NewsSource] = [
    NewsSource(
        name="123telugu",
        url="https://www.123telugu.com/category/mnews/",
        article_selector="article",
        title_selector="h2 a, h3 a",
        link_selector="h2 a, h3 a",
        content_selector="p",
        base_url="https://www.123telugu.com",
        rss_url="https://www.123telugu.com/category/mnews/feed/",
    ),
    NewsSource(
        name="gulte",
        url="https://www.gulte.com/category/movienews",
        article_selector="article, .post-item, li.media",
        title_selector="h2 a, h3 a, .post-title a, .media-heading a",
        link_selector="h2 a, h3 a, .post-title a, .media-heading a",
        content_selector="p, .post-summary, .media-content",
        base_url="https://www.gulte.com",
    ),
    NewsSource(
        name="telugu360",
        url="https://www.telugu360.com/category/movies/",
        article_selector="article, .news-item, .post",
        title_selector="h2 a, h3 a, .entry-title a",
        link_selector="h2 a, h3 a, .entry-title a",
        content_selector="p, .entry-summary",
        base_url="https://www.telugu360.com",
    ),
    NewsSource(
        name="greatandhra",
        url="https://www.greatandhra.com/category/movies/",
        article_selector="article, .post, .news-item",
        title_selector="h2 a, h3 a, .post-title a",
        link_selector="h2 a, h3 a, .post-title a",
        content_selector="p, .post-excerpt",
        base_url="https://www.greatandhra.com",
    ),
    NewsSource(
        name="telugufilmnagar",
        url="https://www.telugufilmnagar.com/category/movie-news/",
        article_selector="article, .post, .news-item",
        title_selector="h2 a, h3 a, .entry-title a",
        link_selector="h2 a, h3 a, .entry-title a",
        content_selector="p, .entry-summary",
        base_url="https://www.telugufilmnagar.com",
    ),
]


def get_sources() -> List[NewsSource]:
    """Return the list of enabled news sources."""
    return [s for s in DEFAULT_SOURCES if s.enabled]
