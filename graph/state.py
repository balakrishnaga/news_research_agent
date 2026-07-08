"""LangGraph state definitions for the Telugu Movie News Agent."""

from typing import Any, Dict, List, Optional, TypedDict


class NewsState(TypedDict):
    """Shared state across the LangGraph workflow."""

    # Input / Config
    sources: List[str]
    max_words: int
    min_words: int
    max_iterations: int
    max_stories: int
    demo_mode: bool

    # Scraping
    raw_articles: List[Dict[str, Any]]  # Articles from all sources

    # Story management
    stories: List[Dict[str, Any]]       # Distinct stories identified
    current_story_index: int            # Which story is being processed
    current_story: Dict[str, Any]       # The active story's facts

    # Per-story generation (reused each loop)
    headline: str
    article: str
    tags: List[str]
    image_url: Optional[str]
    review_feedback: Optional[str]
    iteration_count: int
    approved: bool

    # Accumulated output
    generated_articles: List[Dict[str, Any]]
    final_output: Optional[Dict[str, Any]]
