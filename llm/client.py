"""Pluggable LLM client supporting OpenAI and Ollama backends."""

import os
from typing import Optional

import yaml
from langchain_core.language_models.base import BaseLanguageModel
from langchain_openai import ChatOpenAI
from langchain_ollama import ChatOllama
from langchain_groq import ChatGroq


def load_config(path: str = "config.yaml") -> dict:
    """Load YAML configuration."""
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_llm(config_path: str = "config.yaml") -> BaseLanguageModel:
    """
    Get the configured LLM instance.
    Supports 'openai' and 'ollama' providers.
    """
    config = load_config(config_path)
    llm_config = config.get("llm", {})
    provider = llm_config.get("provider", "openai").lower()

    if provider == "openai":
        openai_cfg = llm_config.get("openai", {})
        api_key = openai_cfg.get("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError(
                "OPENAI_API_KEY not found. Please set it in config.yaml under llm.openai.OPENAI_API_KEY "
                "or set the OPENAI_API_KEY environment variable."
            )
        return ChatOpenAI(
            model=openai_cfg.get("model", "gpt-4o-mini"),
            temperature=openai_cfg.get("temperature", 0.7),
            api_key=api_key, # type: ignore
        )

    elif provider == "ollama":
        ollama_cfg = llm_config.get("ollama", {})
        return ChatOllama(
            model=ollama_cfg.get("model", "llama3"),
            temperature=ollama_cfg.get("temperature", 0.7),
            base_url=ollama_cfg.get("base_url", "http://localhost:11434"),
        )
    elif provider == "groq":
        groq_cfg = llm_config.get("groq", {})
        api_key = groq_cfg.get("GROQ_API_KEY") or os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError(
                "GROQ_API_KEY not found. Please set it in config.yaml under llm.groq.GROQ_API_KEY "
                "or set the GROQ_API_KEY environment variable."
            )
        return ChatGroq(
            model=groq_cfg.get("model", "llama-3.3-70b-versatile"),
            temperature=groq_cfg.get("temperature", 0.7),
            api_key=api_key, # type: ignore
            timeout=groq_cfg.get("timeout", 60),
            max_retries=groq_cfg.get("max_retries", 5),
        )
    elif provider == "kimchi":
        kimchi_cfg = llm_config.get("kimchi", {})
        api_key = kimchi_cfg.get("KIMCHI_API_KEY") or os.getenv("KIMCHI_API_KEY")
        if not api_key:
            raise ValueError(
                "KIMCHI_API_KEY not found. Please set it in config.yaml under llm.kimchi.KIMCHI_API_KEY "
                "or set the KIMCHI_API_KEY environment variable."
            )
        return ChatOpenAI(
            model=kimchi_cfg.get("model", "kimi-k2.6"),
            temperature=kimchi_cfg.get("temperature", 0.7),
            api_key=api_key, # type: ignore
            base_url="https://llm.kimchi.dev/openai/v1",
        )
    else:
        raise ValueError(f"Unsupported LLM provider: {provider}. Use 'openai', 'ollama', 'groq', or 'kimchi'.")
