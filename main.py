"""Entry point for the Telugu Movie News Agent.

Usage:
    python main.py
    OPENAI_API_KEY=sk-xxx python main.py
    python main.py --config custom_config.yaml
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict

from dotenv import load_dotenv

# Load environment variables from .env file first
load_dotenv()

from graph.builder import build_graph
from graph.state import NewsState

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def load_config(path: str = "config.yaml") -> Dict[str, Any]:
    """Load configuration from YAML file."""
    import yaml

    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def build_initial_state(config: Dict[str, Any]) -> NewsState:
    """Construct the initial LangGraph state from configuration."""
    article_cfg = config.get("article", {})
    review_cfg = config.get("review", {})

    return {
        "sources": [],
        "max_words": article_cfg.get("max_words", 250),
        "min_words": article_cfg.get("min_words", 180),
        "max_iterations": review_cfg.get("max_iterations", 3),
        "max_stories": config.get("max_stories", 10),
        "demo_mode": False,
        # Scraping - each article is separate
        "raw_articles": [],
        # Story management - NO MERGING
        "stories": [],
        "current_story_index": 0,
        "current_story": None, # type: ignore
        # Per-story generation (reused each loop)
        "verified_facts": {},
        "unconfirmed_facts": [],
        "confidence": "",
        "headline": "",
        "article": "",
        "tags": [],
        "image_url": None,
        "review_feedback": None,
        "iteration_count": 0,
        "approved": False,
        # Accumulated output - each story separate
        "generated_articles": [],
        "all_stories_done": False,
        "final_output": None,
    }


def save_output(final_output: Dict[str, Any], output_dir: str = "output") -> str:
    """Save the final articles to a JSON file."""
    os.makedirs(output_dir, exist_ok=True)
    outfile = os.path.join(
        output_dir, f"articles_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )
    final_output["generated_at"] = datetime.now(timezone.utc).isoformat()
    with open(outfile, "w", encoding="utf-8") as f:
        json.dump(final_output, f, indent=2, ensure_ascii=False)
    logger.info("Saved output to %s", outfile)
    return outfile


def print_article(final_output: Dict[str, Any]) -> None:
    """Pretty-print the final articles to the console.

    Each story is printed separately - NO MERGING.
    """
    articles = final_output.get("articles", [])
    if not articles:
        # Fallback: single article format
        articles = [{
            "headline": final_output.get("headline", "N/A"),
            "article": final_output.get("article", "N/A"),
            "word_count": final_output.get("word_count", 0),
            "headline_length": final_output.get("headline_length", 0),
            "seo_score": final_output.get("seo_score", 0),
            "source": "unknown",
        }]

    total = final_output.get("total_articles", len(articles))

    print("\n" + "=" * 70)
    print(f" 🇮🇳  TELUGU MOVIE NEWS AGENT — {total} ARTICLES ".center(70))
    print("=" * 70)
    print(f"\n✅ Each article is from a SEPARATE story — NO MERGING applied")
    print(f"📊 Total stories processed: {final_output.get('total_stories', total)}")
    print("=" * 70)

    for i, art in enumerate(articles, 1):
        print(f"\n{'─' * 70}")
        print(f" 📰 ARTICLE {i} of {total} ".center(70))
        print(f"{'─' * 70}")
        print(f"\n📰 HEADLINE ({art.get('headline_length', 0)} chars | SEO: {art.get('seo_score', 0)}/100)")
        print("-" * 70)
        print(art.get("headline", "N/A"))
        print(f"\n📝 ARTICLE ({art.get('word_count', 0)} words)")
        print("-" * 70)
        print(art.get("article", "N/A"))
        print(f"\n🔍 CONFIDENCE: {art.get('confidence', 'N/A').upper()}")
        print(f"🔗 SOURCE: {art.get('source', 'N/A')}")
        if art.get("source_url"):
            print(f"   URL: {art.get('source_url')}")
        if art.get("image_url"):
            print(f"🖼️  IMAGE: {art.get('image_url')}")
        if art.get("tags"):
            print(f"🏷️  TAGS: {', '.join(art.get('tags', []))}")

    print(f"\n{'=' * 70}")
    print(f"📁 Saved to: {final_output.get('output_file', 'N/A')}")
    print("=" * 70 + "\n")


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Agentic AI that scrapes Telugu movie news and writes SEO-optimized articles."
    )
    parser.add_argument(
        "--config",
        type=str,
        default="config.yaml",
        help="Path to YAML configuration file (default: config.yaml)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="output",
        help="Directory to save generated articles (default: output)",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Use mock/demo data instead of live scraping (great for testing without API calls)",
    )
    parser.add_argument(
        "--skip-api-check",
        action="store_true",
        help="Skip OpenAI API key validation (useful when running in demo mode)",
    )
    args = parser.parse_args()

    # Check config exists
    if not os.path.isfile(args.config):
        logger.error("Config file not found: %s", args.config)
        return 1

    # Expose config path so nodes can read it
    os.environ["CONFIG_PATH"] = os.path.abspath(args.config)

    config = load_config(args.config)
    logger.info("Loaded config from %s", args.config)

    # Validate API key for the configured provider (can be skipped in demo mode)
    llm_cfg = config.get("llm", {})
    provider = llm_cfg.get("provider", "openai").lower()
    api_key_missing = False
    api_key_name = None

    if provider == "openai" and not os.getenv("OPENAI_API_KEY"):
        api_key_missing = True
        api_key_name = "OPENAI_API_KEY"
    elif provider == "kimchi" and not os.getenv("KIMCHI_API_KEY"):
        api_key_missing = True
        api_key_name = "KIMCHI_API_KEY"

    if api_key_missing and not args.skip_api_check:
        if args.demo:
            logger.warning(
                "Demo mode active but no %s found. "
                "The demo data imports fine, but LLM nodes (fact verify, headline, article, review) "
                "require an API key or Ollama to actually generate output.",
                api_key_name,
            )
        else:
            logger.error(
                "%s environment variable is required when using '%s' provider.\n"
                "Set it with: export %s='your-key-here'\n"
                "Or switch to 'ollama' in config.yaml.\n"
                "For testing without an API key, use: python main.py --demo --skip-api-check",
                api_key_name, provider, api_key_name,
            )
            return 1

    # Build graph and initial state
    logger.info("Building LangGraph workflow...")
    graph = build_graph()
    initial_state = build_initial_state(config)
    initial_state["demo_mode"] = args.demo

    # Run the workflow with increased recursion limit for multiple stories
    logger.info("Running workflow...")
    try:
        # Calculate recursion limit: ~10 steps per story (scrape, facts, headline, write, review, advance)
        # plus buffer for review iterations. 200 is safe for up to ~20 stories.
        config = {"recursion_limit": 200}
        final_state = graph.invoke(initial_state, config=config)  # type: ignore
    except Exception as exc:
        logger.exception("Workflow failed: %s", exc)
        return 1

    final_output = final_state.get("final_output")
    if not final_output:
        logger.error("No final output produced.")
        return 1

    # Save and display
    output_file = save_output(final_output, output_dir=args.output_dir)
    final_output["output_file"] = output_file
    print_article(final_output)

    return 0


if __name__ == "__main__":
    sys.exit(main())
