"""Web scraping engine for Telugu movie news."""

import email.utils
import logging
import random
import re
import time
import xml.etree.ElementTree as ET
from datetime import date, datetime
from typing import Dict, List, Optional
from urllib.parse import urljoin, urlparse
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

from .sources import NewsSource

logger = logging.getLogger(__name__)


class NewsScraper:
    """Scrape latest Telugu movie news from configured sources."""

    def __init__(self, timeout: int = 15, user_agents: Optional[List[str]] = None):
        self.timeout = timeout
        self.user_agents = user_agents or [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            " (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
            " (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"
            " (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        ]
        self.session = requests.Session()

    def _headers(self) -> Dict[str, str]:
        return {
            "User-Agent": random.choice(self.user_agents),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
        }

    def fetch(self, url: str) -> Optional[str]:
        """Fetch raw HTML from a URL."""
        try:
            logger.info("Fetching %s", url)
            resp = self.session.get(url, headers=self._headers(), timeout=self.timeout)
            resp.raise_for_status()
            return resp.text
        except requests.RequestException as exc:
            logger.warning("Failed to fetch %s: %s", url, exc)
            return None

    def extract_articles(self, html: str, source: NewsSource) -> List[Dict]:
        """Extract article snippets from a source's listing page."""
        if not html:
            return []

        soup = BeautifulSoup(html, "html.parser")
        articles = []

        for elem in soup.select(source.article_selector):
            title_tag = elem.select_one(source.title_selector)
            if not title_tag:
                continue

            title = title_tag.get_text(strip=True)
            link_tag = elem.select_one(source.link_selector)
            href = link_tag.get("href") if link_tag else None
            if href and not href.startswith("http"):
                href = urljoin(source.base_url, href)

            # Skip non-article links (tags, authors, etc.)
            if href and not self._is_article_url(href, source.name):
                continue

            content_tags = elem.select(source.content_selector)
            summary = " ".join(tag.get_text(strip=True) for tag in content_tags[:3])

            # Try to extract a hero/thumbnail image
            image_url: Optional[str] = None
            img_tag = elem.find("img")
            if img_tag:
                img_src = img_tag.get("data-src") or img_tag.get("src") or img_tag.get("data-original")
                if img_src:
                    image_url = urljoin(source.base_url, img_src)

            articles.append({
                "source": source.name,
                "title": title,
                "url": href,
                "summary": summary,
                "content": "",
                "image_url": image_url,
            })

        return articles

    def _is_article_url(self, url: str, source_name: str) -> bool:
        """Heuristic to filter out tag/author/category links."""
        path = urlparse(url).path.lower()
        noise = ["/tag/", "/author/", "/category/", "/page/", "/actor/", "/director/"]
        return not any(n in path for n in noise)

    def _scrape_rss(self, rss_url: str, source_name: str, max_articles: int = 5) -> List[Dict]:
        """Fetch and parse a site-specific RSS feed into articles."""
        try:
            logger.info("Fetching RSS %s", rss_url)
            resp = self.session.get(rss_url, headers=self._headers(), timeout=self.timeout)
            resp.raise_for_status()
        except requests.RequestException as exc:
            logger.warning("Failed to fetch RSS %s: %s", rss_url, exc)
            return []

        articles = []
        ns = {"content": "http://purl.org/rss/1.0/modules/content/", "media": "http://search.yahoo.com/mrss/"}
        try:
            root = ET.fromstring(resp.text)
            channel = root.find("channel")
            if channel is None:
                return articles

            items = channel.findall("item")[:max_articles]
            for item in items:
                title = item.findtext("title", default="").strip()
                link = item.findtext("link", default="").strip()
                description = item.findtext("description", default="").strip()
                pub_date = item.findtext("pubDate", default="").strip()

                if not title or not link:
                    continue

                # Strip HTML tags from description for a plain-text summary
                summary_soup = BeautifulSoup(description, "html.parser")
                summary = summary_soup.get_text(strip=True)

                # Extract image URL from RSS item
                image_url: Optional[str] = None

                # 1. Try media:content or media:thumbnail
                media_elem = item.find("media:content", ns) or item.find("media:thumbnail", ns)
                if media_elem is not None:
                    image_url = media_elem.get("url")

                # 2. Try enclosure
                if not image_url:
                    enclosure = item.find("enclosure")
                    if enclosure is not None and enclosure.get("type", "").startswith("image/"):
                        image_url = enclosure.get("url")

                # 3. Try content:encoded (WordPress extended content)
                if not image_url:
                    content_encoded = item.find("content:encoded", ns)
                    if content_encoded is not None and content_encoded.text:
                        m = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', content_encoded.text)
                        if m:
                            image_url = m.group(1)

                # 4. Fallback: first image in description HTML
                if not image_url:
                    m = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', description)
                    if m:
                        image_url = m.group(1)

                articles.append({
                    "source": source_name,
                    "title": title,
                    "url": link,
                    "summary": summary,
                    "content": "",
                    "published": pub_date,
                    "image_url": image_url,
                })
        except ET.ParseError as exc:
            logger.warning("RSS parse error for %s: %s", rss_url, exc)

        logger.info("RSS '%s' yielded %d articles", source_name, len(articles))
        return articles

    def fetch_article_content(self, url: str) -> str:
        """Fetch full content of a single article page."""
        html = self.fetch(url)
        if not html:
            return ""
        soup = BeautifulSoup(html, "html.parser")

        # Remove script, style, nav, footer, aside
        for tag in soup(["script", "style", "nav", "footer", "aside", "header"]):
            tag.decompose()

        # Try common content selectors
        selectors = [
            "article",
            "[class*='content']",
            "[class*='entry']",
            "[class*='post']",
            ".td-post-content",
            ".entry-content",
            ".post-content",
        ]
        for sel in selectors:
            container = soup.select_one(sel)
            if container:
                paragraphs = container.find_all("p")
                text = "\n".join(p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 40)
                if text:
                    return text

        # Fallback: all paragraphs
        paragraphs = soup.find_all("p")
        return "\n".join(p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 40)

    def extract_date(self, html: str, source_name: str) -> Optional[date]:
        """Extract publication date from article HTML."""
        if not html:
            return None

        soup = BeautifulSoup(html, "html.parser")

        # Strategy 1: Open Graph meta tag
        og_time = soup.find("meta", property="article:published_time")
        if og_time and og_time.get("content"):
            parsed = self._parse_iso_date(og_time["content"])
            if parsed:
                return parsed

        # Strategy 2: Schema.org meta tag
        schema_time = soup.find("meta", attrs={"name": "datePublished"})
        if schema_time and schema_time.get("content"):
            parsed = self._parse_iso_date(schema_time["content"])
            if parsed:
                return parsed

        # Strategy 3: <time datetime="...">
        time_tag = soup.find("time", datetime=True)
        if time_tag and time_tag.get("datetime"):
            parsed = self._parse_iso_date(time_tag["datetime"])
            if parsed:
                return parsed

        # Strategy 4: Human-readable patterns on the page
        text = soup.get_text(separator=" ", strip=True)
        patterns = [
            r"(\d{1,2})\s+([A-Za-z]{3,9})\s+(\d{4})",           # "21 June 2026"
            r"([A-Za-z]{3,9})\s+(\d{1,2}),?\s+(\d{4})",          # "June 21, 2026"
            r"(\d{2})-(\d{2})-(\d{4})",                           # "21-06-2026"
            r"(\d{2})/(\d{2})/(\d{4})",                           # "21/06/2026"
            r"(\d{4})-(\d{2})-(\d{2})",                           # "2026-06-21" inline
        ]
        month_names = {
            "january": 1, "february": 2, "march": 3, "april": 4,
            "may": 5, "june": 6, "july": 7, "august": 8,
            "september": 9, "october": 10, "november": 11, "december": 12,
            "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6,
            "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
        }

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                groups = match.groups()
                try:
                    # Try "21 June 2026"
                    if groups[1].lower() in month_names:
                        d, m_str, y = int(groups[0]), groups[1].lower(), int(groups[2])
                        return date(y, month_names[m_str], d)
                except (ValueError, IndexError):
                    pass
                try:
                    # Try "June 21, 2026"
                    if groups[0].lower() in month_names:
                        m_str, d, y = groups[0].lower(), int(groups[1]), int(groups[2])
                        return date(y, month_names[m_str], d)
                except (ValueError, IndexError):
                    pass
                try:
                    # Try DD-MM-YYYY, MM/DD/YYYY, or YYYY-MM-DD
                    first_len = len(groups[0])
                    if first_len == 4:
                        # YYYY-MM-DD or YYYY/MM/DD
                        y, m, d = int(groups[0]), int(groups[1]), int(groups[2])
                    elif first_len == 2:
                        # DD-MM-YYYY or MM/DD/YYYY — prefer DD-MM for Telugu sites
                        d, m, y = int(groups[0]), int(groups[1]), int(groups[2])
                    else:
                        continue
                    return date(y, m, d)
                except (ValueError, IndexError):
                    pass

        return None

    def _parse_iso_date(self, raw: str) -> Optional[date]:
        """Parse ISO-like date string to date object."""
        raw = raw.strip()
        if not raw:
            return None
        try:
            # Remove timezone info for fromisoformat compatibility
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            return dt.date()
        except ValueError:
            pass
        try:
            # Fallback: parse up to first space (handles "2026-06-21 08:30:00" without timezone)
            dt = datetime.strptime(raw[:10], "%Y-%m-%d")
            return dt.date()
        except (ValueError, IndexError):
            pass
        return None

    def filter_current_date(
        self,
        articles: List[Dict],
        fallback_days: int = 0,
        timezone_name: str = "Asia/Kolkata",
    ) -> List[Dict]:
        """Return only articles published today (in target timezone) or within fallback_days."""
        if not articles:
            return []

        tz = ZoneInfo(timezone_name)
        today = datetime.now(tz).date()
        min_date = today - __import__("datetime").timedelta(days=fallback_days)

        filtered = []
        for art in articles:
            art_date = art.get("article_date")
            if art_date is not None and min_date <= art_date <= today:
                filtered.append(art)
            else:
                if art_date is None:
                    logger.info("Excluding article (no date): %s", art.get("title", "unknown"))
                else:
                    logger.info(
                        "Excluding old article (%s, not in %s–%s): %s",
                        art_date, min_date, today, art.get("title", "unknown"),
                    )

        logger.info(
            "Date filter: %d of %d articles match %s (fallback_days=%d)",
            len(filtered), len(articles), today, fallback_days,
        )
        return filtered

    def scrape_source(self, source: NewsSource, max_articles: int = 5) -> List[Dict]:
        """Scrape a single source and return article snippets with date extraction."""
        html = self.fetch(source.url)
        articles = []
        if html:
            articles = self.extract_articles(html, source)[:max_articles]

        # Fallback to RSS feed when HTML scraping yields nothing and an RSS URL is configured
        if not articles and source.rss_url:
            logger.info("HTML scraping yielded 0 for '%s', trying site RSS fallback...", source.name)
            articles = self._scrape_rss(source.rss_url, source.name, max_articles=max_articles)

        for art in articles:
            if art.get("url"):
                time.sleep(random.uniform(0.5, 1.5))  # Be polite
                full = self.fetch_article_content(art["url"])
                art["content"] = full

                # Extract date from article page
                if art.get("published"):
                    # RSS already provided a date; normalize it
                    try:
                        dt = email.utils.parsedate_to_datetime(art["published"])
                        art["article_date"] = dt.date()
                    except (ValueError, TypeError):
                        article_html = self.fetch(art["url"])
                        art["article_date"] = self.extract_date(article_html, source.name)
                else:
                    article_html = self.fetch(art["url"])
                    art["article_date"] = self.extract_date(article_html, source.name)
        return articles

    def scrape_all(
        self,
        sources: List[NewsSource],
        max_articles_per_source: int = 5,
        date_filter_enabled: bool = False,
        fallback_days: int = 0,
    ) -> List[Dict]:
        """Scrape all sources and return combined articles, optionally filtered by date."""
        all_articles = []
        for src in sources:
            articles = self.scrape_source(src, max_articles=max_articles_per_source)
            all_articles.extend(articles)
            logger.info("Source '%s' yielded %d articles", src.name, len(articles))

        if date_filter_enabled:
            all_articles = self.filter_current_date(
                all_articles, fallback_days=fallback_days
            )
        return all_articles
