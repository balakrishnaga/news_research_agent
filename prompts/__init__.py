"""Prompt templates for the Telugu Movie News Agent."""

import os


def load_prompt(name: str) -> str:
    """Load a prompt template from the prompts directory."""
    path = os.path.join(os.path.dirname(__file__), f"{name}.txt")
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


HEADLINE_PROMPT = load_prompt("headline")
ARTICLE_PROMPT = load_prompt("article")
REVIEW_PROMPT = load_prompt("review")
VERIFY_PROMPT = load_prompt("verify")
