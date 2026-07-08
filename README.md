# 🎬 Movie News Agent

An **Agentic AI** system built with **LangGraph** and **LangChain** that scrapes the latest Telugu cinema news, cross-verifies facts, and writes engaging, SEO-optimized articles (≤250 words) with plagiarism-free headlines.

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| **Multi-Source Scraping** | Fetches news from 5+ leading Telugu cinema sites |
| **Fact Verification** | Cross-checks facts across sources to prevent hallucination |
| **SEO Headlines** | Generates click-worthy, SERP-optimized headlines (40-70 chars) |
| **Plagiarism-Free** | Rephrases content; never copies headlines verbatim |
| **Quality Review Loop** | Built-in editor node with auto-rewrite (max 3 iterations) |
| **Pluggable LLM** | Switch between **OpenAI** and **Ollama** via config |

---

## 🚀 Quick Start

### 1. Clone & Install

```bash
git clone <repo-url>
cd telugu_news_research_agent
pip install -r requirements.txt
```

### 2. Configure

Edit `config.yaml` to choose your LLM provider:

```yaml
llm:
  provider: "openai"   # or "ollama"
  openai:
    model: "gpt-4o-mini"
  ollama:
    model: "llama3"
    base_url: "http://localhost:11434"
```

### 3. Set API Key (OpenAI only)

```bash
export OPENAI_API_KEY="sk-xxxxxxxxxxxxxxxxxxxxxxxx"
```

### 4. Run

```bash
python main.py
```

The agent will:
1. Scrape latest Telugu movie news
2. Extract and verify facts
3. Generate an SEO headline
4. Write a ≤250-word article
5. Auto-review and refine
6. Save results to `output/article_YYYYMMDD_HHMMSS.json`

---

## 🏗 Architecture

```
START
  │
  ▼
┌─────────────────┐
│  scrape_news    │  ← requests + BeautifulSoup
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  verify_facts   │  ← LLM cross-verification
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ generate_headline│  ← SEO + rephrasing
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  write_article  │  ← ≤250 words, engaging tone
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  review_article │  ← fact-check + word count + SEO
└────────┬────────┘
         │
    ┌────┴────┐
    ▼         ▼
 rewrite   finalize
 (loop)      │
             ▼
      build_final_output  →  output/*.json
             │
            END
```

---

## 📁 Project Structure

```
telugu_news_research_agent/
├── main.py              # Entry point
├── config.yaml          # All configuration
├── requirements.txt
├── README.md
│
├── graph/               # LangGraph workflow
│   ├── state.py         # TypedDict state schema
│   ├── nodes.py         # Node implementations
│   └── builder.py       # Graph compiler
│
├── scraper/             # Web scraping
│   ├── sources.py       # News source configs
│   └── engine.py        # Scraper implementation
│
├── prompts/             # LLM prompt templates
│   ├── headline.txt
│   ├── article.txt
│   ├── review.txt
│   └── verify.txt
│
├── llm/                 # Pluggable LLM client
│   └── client.py
│
├── utils/               # Helpers
│   └── helpers.py
│
└── output/              # Generated articles
```

---

## ⚙️ Configuration

Key settings in `config.yaml`:

| Section | Key | Description |
|---------|-----|-------------|
| `llm` | `provider` | `openai` or `ollama` |
| `llm.openai` | `model` | e.g., `gpt-4o-mini`, `gpt-4o` |
| `llm.ollama` | `model` | e.g., `llama3`, `qwen2.5` |
| `scraping` | `max_sources` | How many sites to scrape (default: 3) |
| `article` | `max_words` | Article length limit (default: 250) |
| `article` | `min_words` | Article minimum length (default: 180) |
| `review` | `max_iterations` | Max rewrite attempts (default: 3) |

---

## 🛡 Hallucination Prevention

1. **Source anchoring**: LLM is instructed to use ONLY verified facts
2. **Cross-verification**: Facts appearing in 2+ sources are marked "verified"
3. **Review node**: Dedicated LLM check against original sources
4. **Citation requirement**: Prompts explicitly forbid inventing names, dates, or numbers

---

## 📜 Output Format

```json
{
  "headline": "NTR's Devara Storms Box Office: Day 1 Collections Cross 80 Crores!",
  "article": "The wait is finally over! Jr NTR...",
  "word_count": 248,
  "headline_length": 68,
  "seo_score": 92,
  "sources": [
    "https://www.123telugu.com/...",
    "https://www.greatandhra.com/..."
  ],
  "confidence": "high",
  "verified_facts": {
    "movie_title": "Devara",
    "actors": ["Jr NTR"],
    ...
  },
  "generated_at": "2026-06-07T10:00:00Z",
  "output_file": "output/article_20260607_100000.json"
}
```

---

## 🔄 Swapping LLM Backends

### OpenAI (Cloud, Best Quality)
```yaml
llm:
  provider: "openai"
  openai:
    model: "gpt-4o-mini"
```
Requires `OPENAI_API_KEY` env var.

### Ollama (Local, Free)
```yaml
llm:
  provider: "ollama"
  ollama:
    model: "llama3"
```
Requires [Ollama](https://ollama.com) running locally.

---

## 🛠 Development

Run with a custom config:
```bash
python main.py --config custom_config.yaml --output-dir ./my_articles
```

---

## 📄 License

MIT License
