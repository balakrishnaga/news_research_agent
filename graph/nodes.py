"""LangGraph node implementations for the Telugu Movie News Agent."""

import json
import logging
import os
import re
import time
from typing import Any, Dict, List

from langchain_core.language_models.base import BaseLanguageModel

from graph.state import NewsState
from llm.client import get_llm
from prompts import ARTICLE_PROMPT, HEADLINE_PROMPT, REVIEW_PROMPT, VERIFY_PROMPT
from scraper.engine import NewsScraper
from scraper.images import GoogleImageSearcher
from scraper.rss_fallback import fallback_articles
from scraper.sources import get_sources
from utils.helpers import count_words, score_headline_seo, validate_word_count

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def _load_config() -> Dict[str, Any]:
    import yaml
    path = os.environ.get("CONFIG_PATH", "config.yaml")
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _llm_request_delay() -> float:
    """Return configured delay between LLM requests to avoid rate limits."""
    try:
        cfg = _load_config()
        return cfg.get("llm", {}).get("request_delay", 0.0)
    except Exception:
        return 0.0


def _invoke_llm_json(llm: BaseLanguageModel, prompt: str) -> Dict[str, Any]:
    """Invoke LLM and try to parse JSON output.

    Handles edge cases like markdown fences, extra text wrapping,
    list responses, and models that add commentary around JSON.
    """
    delay = _llm_request_delay()
    if delay > 0:
        time.sleep(delay)
    response = llm.invoke(prompt)
    raw = response.content if hasattr(response, "content") else str(response)
    raw = raw.strip()

    # Strategy 1: Try direct parse
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        # Strategy 2: Extract first JSON block from markdown
        fences = re.findall(r"```(?:json)?\s*(.*?)\s*```", raw, re.DOTALL)
        for candidate in fences:
            try:
                parsed = json.loads(candidate.strip())
                break
            except json.JSONDecodeError:
                continue
        else:
            # Strategy 3: Try to find a raw JSON object/array
            # Find first { or [ and last } or ]
            obj_match = re.search(r"\{.*\}", raw, re.DOTALL)
            arr_match = re.search(r"\[.*\]", raw, re.DOTALL)
            candidate = ""
            if obj_match:
                candidate = obj_match.group(0)
            elif arr_match:
                candidate = arr_match.group(0)
            try:
                parsed = json.loads(candidate.strip())
            except (json.JSONDecodeError, ValueError) as exc:
                raise ValueError(f"Could not parse JSON from response: {raw[:500]}...") from exc

    # If the model returned a list instead of a dict, convert gracefully
    if isinstance(parsed, list):
        logger.warning("LLM returned a JSON list; converting to expected dict format.")
        return {
            "verified_facts": {"summary": "\n".join(str(item) for item in parsed[:3])},
            "unconfirmed_facts": [str(item) for item in parsed[3:]] if len(parsed) > 3 else [],
            "confidence": "medium",
        }

    if not isinstance(parsed, dict):
        raise ValueError(f"Expected JSON object, got {type(parsed).__name__}: {raw[:500]}...")

    return parsed


def _invoke_llm_text(llm: BaseLanguageModel, prompt: str) -> str:
    """Invoke LLM and return plain text."""
    delay = _llm_request_delay()
    if delay > 0:
        time.sleep(delay)
    response = llm.invoke(prompt)
    return response.content if hasattr(response, "content") else str(response)


# --------------------------------------------------------------------------- #
# Nodes
# --------------------------------------------------------------------------- #

def scrape_news(state: NewsState) -> NewsState:
    """Scrape Telugu movie news from configured sources or use demo data.

    This node only runs once at the start. If stories already exist, skip re-scraping.
    """
    # SAFETY: Don't re-scrape if we already have stories
    existing_stories = state.get("stories", [])
    if existing_stories:
        logger.info("Stories already exist (%d), skipping re-scrape", len(existing_stories))
        return state

    # If all stories are done, don't scrape again
    if state.get("all_stories_done", False):
        logger.info("All stories already done, skipping scrape")
        return state

    # Demo mode: bypass live scraping entirely
    if state.get("demo_mode", False):
        logger.info("Demo mode active — using mock Telugu movie news data.")
        from demo_data import MOCK_ARTICLES
        # Each article is its own story - no merging
        stories = [{
            "article": art,
            "verified_facts": None,
            "headline": None,
            "content": None,
            "image_url": art.get("image_url"),
            "tags": [],
        } for art in MOCK_ARTICLES]
        return {
            **state,
            "raw_articles": MOCK_ARTICLES,
            "stories": stories,
            "current_story_index": 0,
            "current_story": stories[0] if stories else None,
        }

    config = _load_config()
    scrape_cfg = config.get("scraping", {})
    timeout = scrape_cfg.get("timeout", 15)
    max_src = scrape_cfg.get("max_sources", 3)
    user_agents = scrape_cfg.get("user_agents")

    # Date filter config
    date_filter_cfg = config.get("date_filter", {})
    date_filter_enabled = date_filter_cfg.get("enabled", False)
    fallback_days = date_filter_cfg.get("fallback_days", 0)

    scraper = NewsScraper(timeout=timeout, user_agents=user_agents)
    sources = get_sources()[:max_src]

    if not sources:
        logger.warning("No enabled news sources found.")
        return {**state, "raw_articles": [], "stories": []}

    articles = scraper.scrape_all(
        sources,
        max_articles_per_source=5,
        date_filter_enabled=date_filter_enabled,
        fallback_days=fallback_days,
    )

    # RSS fallback if direct scraping yielded nothing
    if not articles:
        logger.warning("Direct scraping returned 0 articles. Trying RSS fallback...")
        articles = fallback_articles(articles, max_results=10)

    # Date filter may have excluded everything
    if not articles:
        logger.warning("No articles match the current-date filter.")
        return {**state, "raw_articles": [], "stories": []}

    # Respect max_stories to stay within the graph recursion budget
    max_stories = state.get("max_stories", 10)
    if len(articles) > max_stories:
        logger.info("Limiting %d scraped articles to max_stories=%d", len(articles), max_stories)
        articles = articles[:max_stories]

    # Each article is its own story - NO MERGING
    stories = [{
        "article": art,
        "verified_facts": None,
        "headline": None,
        "content": None,
        "image_url": art.get("image_url"),
        "tags": [],
    } for art in articles]

    logger.info("Scraped %d articles total. Each will be processed as a separate story.", len(articles))
    return {
        **state,
        "raw_articles": articles,
        "stories": stories,
        "current_story_index": 0,
        "current_story": stories[0] if stories else None,
    }


def verify_facts(state: NewsState) -> NewsState:
    """Use LLM to extract and verify facts for the CURRENT STORY ONLY.

    Each article is processed individually - NO MERGING with other articles.
    """
    # SAFETY: If all stories are done, don't process any more
    if state.get("all_stories_done", False):
        logger.info("All stories already done - skipping verify_facts")
        return state

    current_story = state.get("current_story")
    if not current_story:
        logger.warning("No current story to verify facts from.")
        return {**state, "verified_facts": {}, "unconfirmed_facts": [], "confidence": "low"}

    # Work on this story's article ONLY - never merge with others
    art = current_story.get("article", {})
    if not art:
        logger.warning("Current story has no article data.")
        return {**state, "verified_facts": {}, "unconfirmed_facts": [], "confidence": "low"}

    # Build source summary for JUST THIS ONE ARTICLE
    source_summary = (
        f"Source: {art.get('source', 'unknown')}\n"
        f"Title: {art.get('title', '')}\n"
        f"Summary: {art.get('summary', '')[:1000]}\n"
        f"Content: {art.get('content', '')[:2000]}\n"
    )

    prompt = VERIFY_PROMPT.format(sources=source_summary)

    try:
        llm = get_llm()
        result = _invoke_llm_json(llm, prompt)
        verified_facts = result.get("verified_facts", {})

        # Update the current story with verified facts and tags
        current_story["verified_facts"] = verified_facts
        current_story["unconfirmed_facts"] = result.get("unconfirmed_facts", [])
        current_story["confidence"] = result.get("confidence", "low")
        current_story["tags"] = result.get("tags", [])

        # Image search via Google CSE if enabled
        image_cfg = _load_config().get("image_search", {})
        if image_cfg.get("enabled", False):
            api_key = os.getenv("GOOGLE_API_KEY", "")
            cse_id = os.getenv("GOOGLE_CSE_ID", "")
            if api_key and cse_id:
                try:
                    searcher = GoogleImageSearcher(api_key, cse_id, image_cfg)
                    tags = current_story.get("tags", [])
                    headline = current_story.get("headline", "")
                    fallback = current_story.get("article", {}).get("image_url")
                    hero_image = searcher.get_image_for_story(
                        tags=tags,
                        headline=headline,
                        fallback_url=fallback,
                    )
                    current_story["image_url"] = hero_image
                except Exception as exc:
                    logger.warning("Image search failed: %s", exc)
            else:
                logger.warning("Image search enabled but GOOGLE_API_KEY or GOOGLE_CSE_ID not set.")

        # Also update stories list
        stories = state.get("stories", [])
        idx = state.get("current_story_index", 0)
        if stories and idx < len(stories):
            stories[idx] = current_story

        return {
            **state,
            "verified_facts": verified_facts,
            "unconfirmed_facts": result.get("unconfirmed_facts", []),
            "confidence": result.get("confidence", "low"),
            "current_story": current_story,
            "stories": stories,
        }
    except Exception as exc:
        logger.error("Fact verification failed for story: %s", exc)
        # Fallback: use the article's own summary
        fallback_facts = {"summary": art.get("summary", "")}
        current_story["verified_facts"] = fallback_facts
        current_story["confidence"] = "low"
        current_story["tags"] = ["telugu", "cinema", "news"]  # Default tags

        stories = state.get("stories", [])
        idx = state.get("current_story_index", 0)
        if stories and idx < len(stories):
            stories[idx] = current_story

        return {
            **state,
            "verified_facts": fallback_facts,
            "unconfirmed_facts": [],
            "confidence": "low",
            "current_story": current_story,
            "stories": stories,
        }


def generate_headline(state: NewsState) -> NewsState:
    """Generate an SEO-optimized, plagiarism-free headline for the CURRENT STORY."""
    # SAFETY: If all stories are done, don't process any more
    if state.get("all_stories_done", False):
        logger.info("All stories already done - skipping generate_headline")
        return state

    current_story = state.get("current_story")
    facts = current_story.get("verified_facts") if current_story else state.get("verified_facts", {})

    if not facts:
        headline = "Latest Telugu Movie News Update"
        if current_story:
            current_story["headline"] = headline
        return {**state, "headline": headline, "current_story": current_story}

    facts_text = json.dumps(facts, indent=2)
    prompt = HEADLINE_PROMPT.format(facts=facts_text)

    try:
        llm = get_llm()
        headline = _invoke_llm_text(llm, prompt).strip()
        # Clean up
        headline = headline.replace('"', '').replace("'", "").strip()
        if len(headline) > 100:
            headline = headline[:97] + "..."
        logger.info("Generated headline for story %d: %s", state.get("current_story_index", 0), headline)

        # Update current story with headline
        if current_story:
            current_story["headline"] = headline

        return {**state, "headline": headline, "current_story": current_story}
    except Exception as exc:
        logger.error("Headline generation failed: %s", exc)
        headline = "Latest Telugu Cinema News Update"
        if current_story:
            current_story["headline"] = headline
        return {**state, "headline": headline, "current_story": current_story}


def write_article(state: NewsState) -> NewsState:
    """Write the article body for the CURRENT STORY using verified facts only."""
    current_story = state.get("current_story")
    facts = current_story.get("verified_facts") if current_story else state.get("verified_facts", {})
    feedback = state.get("review_feedback")

    facts_text = json.dumps(facts, indent=2)
    prompt = ARTICLE_PROMPT.format(facts=facts_text)

    if feedback:
        prompt += f"\n\nEDITOR FEEDBACK (please address this):\n{feedback}\n"

    try:
        llm = get_llm()
        article = _invoke_llm_text(llm, prompt).strip()
        logger.info("Generated article for story %d (%d words).", state.get("current_story_index", 0), count_words(article))

        # Update current story with content
        if current_story:
            current_story["content"] = article

        return {**state, "article": article, "current_story": current_story}
    except Exception as exc:
        logger.error("Article writing failed: %s", exc)
        summary = facts.get("summary", "Latest update from Telugu cinema.")
        if current_story:
            current_story["content"] = summary
        return {**state, "article": summary, "current_story": current_story}


def review_article(state: NewsState) -> NewsState:
    """Review article quality and factual accuracy for the CURRENT STORY."""
    config = _load_config()
    article_cfg = config.get("article", {})
    min_w = article_cfg.get("min_words", 180)
    max_w = article_cfg.get("max_words", 250)

    current_story = state.get("current_story")
    article = state.get("article", "")
    headline = state.get("headline", "")
    facts = current_story.get("verified_facts") if current_story else state.get("verified_facts", {})

    # Fast-path structural checks
    is_valid_wc, wc = validate_word_count(article, min_w, max_w)
    seo_score, seo_feedback = score_headline_seo(headline)

    # LLM-based deep review
    prompt = REVIEW_PROMPT.format(
        article=article,
        headline=headline,
        facts=json.dumps(facts, indent=2),
        min_words=min_w,
        max_words=max_w,
    )

    approved = False
    issues = []
    try:
        llm = get_llm()
        result = _invoke_llm_json(llm, prompt)
        approved = result.get("approved", False)
        issues = result.get("issues", [])
        feedback = result.get("feedback", "")
    except Exception as exc:
        logger.error("LLM review failed: %s", exc)
        # Local heuristic fallback
        approved = is_valid_wc and seo_score >= 50 and facts
        feedback = f"SEO score: {seo_score}. Word count: {wc}." if approved else "Needs revision."
        if not is_valid_wc:
            issues.append(f"Word count {wc} not in range {min_w}-{max_w}.")
        if seo_score < 50:
            issues.append("Headline SEO score too low.")

    iteration = state.get("iteration_count", 0) + 1
    max_iter = state.get("max_iterations", 3)

    # Force approve if max iterations reached
    if iteration >= max_iter:
        approved = True
        feedback = "Max iterations reached. Finalizing."
        issues = []

    # Update current story with approval status
    if current_story:
        current_story["approved"] = approved
        current_story["content"] = article
        current_story["headline"] = headline

    # Update stories list
    stories = state.get("stories", [])
    idx = state.get("current_story_index", 0)
    if stories and idx < len(stories):
        stories[idx] = current_story

    return {
        **state,
        "approved": approved,
        "review_feedback": feedback if not approved else None,
        "iteration_count": iteration,
        "current_story": current_story,
        "stories": stories,
    }


def advance_story(state: NewsState) -> NewsState:
    """Move to the next story when current one is approved.

    This node is called after a story is approved. It either:
    1. Advances to the next story
    2. Signals all stories are done
    """
    # If already done, don't process any more
    if state.get("all_stories_done", False):
        logger.info("advance_story: already done, returning")
        return state

    stories = state.get("stories", [])
    current_idx = state.get("current_story_index", 0)
    generated = state.get("generated_articles", [])

    # Save the current story's generated article (prevent duplicates)
    current_story = state.get("current_story")
    if current_story and current_story.get("approved"):
        # Check if this story was already saved (by index)
        already_saved = any(
            g.get("source_url") == current_story.get("article", {}).get("url")
            for g in generated
        )
        if not already_saved:
            generated.append({
                "headline": current_story.get("headline", ""),
                "article": current_story.get("content", ""),
                "source": current_story.get("article", {}).get("source", "unknown"),
                "source_url": current_story.get("article", {}).get("url", ""),
                "confidence": current_story.get("confidence", "low"),
                "verified_facts": current_story.get("verified_facts", {}),
                "image_url": current_story.get("image_url"),
                "tags": current_story.get("tags", []),
            })
            logger.info("Story %d approved and saved. Total generated: %d", current_idx + 1, len(generated))
        else:
            logger.info("Story %d already saved, skipping duplicate", current_idx + 1)

    # Check if there are more stories
    next_idx = current_idx + 1
    if next_idx < len(stories):
        logger.info("Moving to story %d of %d", next_idx + 1, len(stories))
        return {
            **state,
            "current_story_index": next_idx,
            "current_story": stories[next_idx],
            "generated_articles": generated,
            "iteration_count": 0,  # Reset iteration for new story
            "review_feedback": None,
            "approved": False,  # Reset approval for new story
            "all_stories_done": False,  # Explicitly False
        }
    else:
        # All stories done - set index to sentinel value (length of stories)
        # so the router can detect completion by checking current_idx >= total
        logger.info("All %d stories processed. Setting all_stories_done=True", len(stories))
        return {
            **state,
            "current_story_index": len(stories),  # Sentinel: indicates all stories processed
            "generated_articles": generated,
            "all_stories_done": True,
        }


def build_final_output(state: NewsState) -> NewsState:
    """Format all generated articles into a structured output.

    Each story is kept separate - NO MERGING.
    """
    generated = state.get("generated_articles", [])
    stories = state.get("stories", [])

    if not generated:
        # Fallback: single article mode
        article = state.get("article", "")
        headline = state.get("headline", "")
        current_story = state.get("current_story", {})
        output = {
            "articles": [{
                "headline": headline,
                "article": article,
                "word_count": count_words(article),
                "headline_length": len(headline),
                "seo_score": score_headline_seo(headline)[0],
                "image_url": current_story.get("image_url"),
                "tags": current_story.get("tags", []),
            }],
            "total_articles": 1,
            "generated_at": None,
        }
        return {**state, "final_output": output}

    # Each story becomes its own article - NO MERGING
    articles_output = []
    for i, gen in enumerate(generated):
        art = gen.get("article", "")
        hl = gen.get("headline", "")
        articles_output.append({
            "story_number": i + 1,
            "headline": hl,
            "article": art,
            "word_count": count_words(art),
            "headline_length": len(hl),
            "seo_score": score_headline_seo(hl)[0],
            "source": gen.get("source", "unknown"),
            "source_url": gen.get("source_url", ""),
            "confidence": gen.get("confidence", "low"),
            "image_url": gen.get("image_url"),
            "tags": gen.get("tags", []),
        })

    output = {
        "articles": articles_output,
        "total_articles": len(articles_output),
        "total_stories": len(stories),
        "generated_at": None,  # filled by caller
    }

    return {**state, "final_output": output}
