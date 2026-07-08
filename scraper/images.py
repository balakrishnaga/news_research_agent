"""Google Image Search via Custom Search Engine API."""

import logging
import math
from typing import Dict, List, Optional

import requests

logger = logging.getLogger(__name__)


def score_candidate(
    width: int,
    height: int,
    target_w: int = 1200,
    target_h: int = 600,
    tolerance: float = 0.2,
) -> float:
    """Score an image candidate by how close it is to target dimensions and aspect ratio."""
    dimension_distance = math.sqrt((width - target_w) ** 2 + (height - target_h) ** 2)
    aspect_ratio = width / max(height, 1)
    ratio_penalty = 0.0
    if not ((2 - tolerance) <= aspect_ratio <= (2 + tolerance)):
        ratio_penalty = 1000.0
    return dimension_distance + ratio_penalty


class GoogleImageSearcher:
    """Search Google Images via Custom Search Engine API."""

    def __init__(
        self,
        api_key: str,
        cse_id: str,
        config: Dict,
    ):
        self.api_key = api_key
        self.cse_id = cse_id
        self.cfg = config.get("google_cse", {})
        self.api_url = self.cfg.get("api_url", "https://www.googleapis.com/customsearch/v1")
        self.num_results = self.cfg.get("num_results", 10)
        self.target_width = self.cfg.get("target_width", 1200)
        self.target_height = self.cfg.get("target_height", 600)
        self.tolerance = config.get("aspect_ratio_tolerance", 0.2)

    def build_query(self, tags: List[str], headline: str = "") -> str:
        """Build a Google Images search query from article tags and headline."""
        parts = tags[:3] if tags else []
        if not parts and headline:
            parts = headline.split()[:5]
        query = " ".join(parts) + " telugu cinema"
        return query.strip()

    def search(self, query: str) -> List[Dict]:
        """Call Google CSE image search and return raw result items."""
        if not self.api_key or not self.cse_id:
            logger.warning("Google CSE API key or CSE ID not configured. Skipping image search.")
            return []

        params = {
            "key": self.api_key,
            "cx": self.cse_id,
            "q": query,
            "searchType": "image",
            "num": min(self.num_results, 10),
            "imgSize": "LARGE",
        }
        try:
            logger.info("Google Images search: %s", query)
            resp = requests.get(self.api_url, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            items = data.get("items", [])
            logger.info("Google Images returned %d results for query: %s", len(items), query)
            return items
        except requests.RequestException as exc:
            logger.warning("Google Images API request failed: %s", exc)
            return []
        except Exception as exc:
            logger.warning("Google Images API error: %s", exc)
            return []

    def find_best_match(self, results: List[Dict]) -> Optional[str]:
        """Return the image URL closest to target dimensions."""
        if not results:
            return None

        best_score = float("inf")
        best_url = None

        for item in results:
            link = item.get("link")
            image_info = item.get("image", {})
            width = image_info.get("width", 0)
            height = image_info.get("height", 0)

            if not link or not width or not height:
                continue

            score = score_candidate(width, height, self.target_width, self.target_height, self.tolerance)
            logger.debug("Image candidate: %s (%dx%d) score=%.1f", link, width, height, score)
            if score < best_score:
                best_score = score
                best_url = link

        if best_score > 800:
            logger.info("No image matched target dimensions closely enough (best score=%.1f)", best_score)
            return None

        logger.info("Best image match: %s (score=%.1f)", best_url, best_score)
        return best_url

    def get_image_for_story(
        self,
        tags: List[str],
        headline: str = "",
        fallback_url: Optional[str] = None,
    ) -> Optional[str]:
        """Search for an image, return best match or fallback."""
        query = self.build_query(tags, headline)
        results = self.search(query)
        best = self.find_best_match(results)
        if best:
            return best

        if fallback_url:
            logger.info("Falling back to article image: %s", fallback_url)
            return fallback_url

        return None
