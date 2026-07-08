"""Utility helpers for text processing, validation, and SEO scoring."""

import re
from typing import Tuple


def count_words(text: str) -> int:
    """Count words in a text string."""
    if not text:
        return 0
    return len(text.split())


def clean_text(text: str) -> str:
    """Clean scraped text by removing extra whitespace, ads markers, etc."""
    if not text:
        return ""
    # Remove extra whitespace
    text = re.sub(r"\s+", " ", text)
    # Remove common ad markers
    text = re.sub(r"\bAd\b", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\bAdvertisement\b", "", text, flags=re.IGNORECASE)
    # Remove special chars but keep basic punctuation
    text = re.sub(r"[^\w\s.,!?()'\"-]", " ", text)
    return text.strip()


def score_headline_seo(headline: str) -> Tuple[int, str]:
    """
    Score an SEO headline on a scale of 0-100.
    Returns (score, feedback).
    """
    if not headline:
        return 0, "Headline is empty."

    score = 0
    feedback_parts = []

    length = len(headline)
    if 40 <= length <= 70:
        score += 30
        feedback_parts.append("✓ Length is optimal for SERP.")
    elif length < 40:
        score += 15
        feedback_parts.append("⚠ Headline is short; consider adding a power word or keyword.")
    else:
        score += 10
        feedback_parts.append("⚠ Headline is long; may be truncated in SERP.")

    # Check for power words
    power_words = {
        "exclusive", "breaking", "update", "confirmed", "official",
        "massive", "shocking", "surprise", "first look", "teaser",
        "trailer", "release", "blockbuster", "record", "collections",
        "box office", "stunning", "leaked", "announcement"
    }
    headline_lower = headline.lower()
    found_power = [w for w in power_words if w in headline_lower]
    if found_power:
        score += 25
        feedback_parts.append(f"✓ Contains power words: {', '.join(found_power)}.")
    else:
        feedback_parts.append("⚠ Add a power word (e.g., Exclusive, Confirmed, Breaking).")

    # Check for numbers
    if re.search(r"\d", headline):
        score += 20
        feedback_parts.append("✓ Contains numbers (good for CTR).")
    else:
        feedback_parts.append("⚠ Consider adding a number (e.g., Day 1, 100 Crores).")

    # Check for movie-related keywords
    movie_keywords = {"movie", "film", "cinema", "hero", "director", "release", "teaser", "trailer"}
    found_movie = [w for w in movie_keywords if w in headline_lower]
    if found_movie:
        score += 15
        feedback_parts.append("✓ Contains movie/cinema keywords.")
    else:
        feedback_parts.append("⚠ Add cinema-related keywords.")

    # Check for actor names (common Telugu)
    telugu_stars = {
        "ntr", "ram charan", "allu arjun", "mahesh babu", "prabhas",
        "pawan kalyan", "chiranjeevi", "nag arjun", "venkatesh",
        "ravi teja", "nani", "dulquer salmaan", "vijay deverakonda"
    }
    found_stars = [s for s in telugu_stars if s in headline_lower]
    if found_stars:
        score += 10
        feedback_parts.append(f"✓ Mentions star: {', '.join(found_stars)}.")
    else:
        feedback_parts.append("⚠ Consider mentioning a star name for searchability.")

    return min(score, 100), " | ".join(feedback_parts)


def validate_word_count(text: str, min_words: int, max_words: int) -> Tuple[bool, int]:
    """Validate that text is within word count bounds."""
    wc = count_words(text)
    return min_words <= wc <= max_words, wc
