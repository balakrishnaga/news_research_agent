"""LangGraph builder: assembles the state machine."""

from langgraph.graph import END, START, StateGraph # type: ignore

from graph.nodes import (
    advance_story,
    build_final_output,
    generate_headline,
    review_article,
    scrape_news,
    verify_facts,
    write_article,
)
from graph.state import NewsState

import logging

logger = logging.getLogger(__name__)


def review_router(state: NewsState) -> str:
    """Route to rewrite or advance based on review outcome."""
    approved = state.get("approved", False)
    current_idx = state.get("current_story_index", 0)
    logger.debug("review_router: approved=%s, story=%d", approved, current_idx + 1)
    if approved:
        return "advance"
    return "rewrite"


def story_router(state: NewsState) -> str:
    """Route to next story or finalize based on story index.

    CRITICAL: This router checks the current index against the total stories
    to determine routing, NOT all_stories_done. This is because LangGraph
    may call the router BEFORE merging the node's state update.
    """
    current_idx = state.get("current_story_index", 0)
    total_stories = len(state.get("stories", []))

    # If current index equals or exceeds total, we're done
    # (current_idx is 0-based, so if current_idx == total_stories, we've processed all)
    is_done = current_idx >= total_stories

    logger.info("story_router: current_idx=%d, total=%d, is_done=%s", current_idx, total_stories, is_done)

    if is_done:
        logger.info("story_router: routing to FINALIZE")
        return "finalize"
    logger.info("story_router: routing to NEXT_STORY (%d of %d)", current_idx + 1, total_stories)
    return "next_story"


def build_graph():
    """Build and return the compiled LangGraph workflow.

    The workflow processes each article as a SEPARATE STORY - NO MERGING.
    After a story is approved, it advances to the next story until all are done.
    """
    workflow = StateGraph(NewsState)

    # Register nodes
    workflow.add_node("scrape_news", scrape_news)
    workflow.add_node("verify_facts", verify_facts)
    workflow.add_node("generate_headline", generate_headline)
    workflow.add_node("write_article", write_article)
    workflow.add_node("review_article", review_article)
    workflow.add_node("advance_story", advance_story)
    workflow.add_node("build_final_output", build_final_output)

    # Define edges - START to scrape
    workflow.add_edge(START, "scrape_news")
    workflow.add_edge("scrape_news", "verify_facts")
    workflow.add_edge("verify_facts", "generate_headline")
    workflow.add_edge("generate_headline", "write_article")
    workflow.add_edge("write_article", "review_article")

    # Conditional edge: review → rewrite or advance to next story
    workflow.add_conditional_edges(
        "review_article",
        review_router,
        {
            "rewrite": "write_article",  # Retry current story
            "advance": "advance_story",  # Move to next story
        },
    )

    # Conditional edge: advance_story → next story OR finalize
    workflow.add_conditional_edges(
        "advance_story",
        story_router,
        {
            "next_story": "verify_facts",  # Process next story from facts
            "finalize": "build_final_output",
        },
    )

    workflow.add_edge("build_final_output", END)

    return workflow.compile()
