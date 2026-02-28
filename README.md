# GEO Experiment — NutreEliya

A controlled scientific experiment measuring **Generative Engine Optimization (GEO)** — how to improve the likelihood that an LLM agent cites your website when performing web-based Q&A with retrieved sources.

## Research Question

> "How does improving a website's content through a GEO lens affect its likelihood of being cited by an LLM agent when included among retrieved web sources?"

## How It Works

1. **Tavily** fetches 10 organic web sources for a given query
2. Our site's content is **injected** at position 5 among those results
3. **GPT-5** (Azure OpenAI) synthesizes an answer from all 11 sources
4. **Citation analysis** determines if the LLM cited our site — explicit citations, depth ranking, n-gram overlap
5. We **benchmark** against winning sources, apply GEO improvements, and re-run

## Results

| Version | Citation Rate | Avg Depth Rank | Key Change |
|---------|-------------|----------------|------------|
| Control (nutreeliya.com) | 0% (0/5) | N/A | Original site, never modified |
| Baseline v0 (local clone) | 0% (0/5) | N/A | Identical to control |
| GEO v1 | 60% (3/5) | #2.0 | +complete recipes, +expert attribution, +stats |
| GEO v2 | **95% (19/20)** | **#1.4** | +comfort food, +substitution guide |

## Project Structure

```
run_batch.py                 — Main batch experiment runner
geo_experiment/
  config.py                  — Env var loading, Azure/LiteLLM config
  agent.py                   — LangChain + LangGraph ReAct agent (chat mode)
  experiment.py              — Experiment pipeline: search → inject → synthesize → analyze
  report.py                  — Rich console + Markdown report generation
main.py                      — CLI entry point (chat / experiment modes)
local_site/                  — Local clone of nutreeliya.com (GEO-optimized)
  index.html                 — GEO v2 optimized homepage
  recipes.html               — Recipes page
  css/style.css              — Stylesheet
  js/main.js                 — JavaScript
site_content/
  nutreeliya_homepage.txt    — Control group content (original, never changes)
  nutreeliya_local_homepage.txt — Experiment group content (GEO-optimized)
reports/
  batch_004_control_group_nutreeliya/    — Control: 0/5 (0%)
  batch_005_experiment_baseline_v0/      — Baseline: 0/5 (0%)
  batch_006_geo_v1_optimized/            — GEO v1: 3/5 (60%)
  batch_007_geo_v2_comfort_food/         — GEO v2: 4/5 (80%)
  batch_008_geo_v2_retest_set_a/         — GEO v2 retest: 5/5 (100%)
  batch_009_geo_v2_retest_set_c/         — GEO v2 retest: 5/5 (100%)
```

## Setup

```bash
# Install dependencies
uv sync

# Configure API keys in .env
TAVILY_API_KEY=...
AZURE_API_BASE=...
AZURE_OPENAI_API_KEY=...
AZURE_DEPLOYMENT_NAME=gpt-5
```

## Usage

```bash
# Run a batch experiment
uv run python run_batch.py <batch_name> <control|experiment> <set_a|set_b|set_c|set_d>

# Examples
uv run python run_batch.py control_run control set_a
uv run python run_batch.py geo_v3_test experiment set_b

# View local site
cd local_site && python -m http.server 8000
```

## Key GEO Findings

**What makes LLMs cite a source:**
- Specific, extractable data (ingredients, macros, step-by-step instructions)
- Named expert attribution with credentials
- Statistical claims with citations
- Practical tips (safety notes, brand recommendations, storage)
- Content that directly matches query intent

**What gets ignored:**
- Self-promotional marketing language ("industry-recognized leader")
- Vague, unverifiable claims ("endorsed by top professionals")
- Generic information the LLM already knows
- Content without extractable details

## Tech Stack

- **LLM:** Azure OpenAI GPT-5 via LiteLLM
- **Search:** Tavily Search API (10 results per query)
- **Agent:** LangChain + LangGraph (ReAct pattern)
- **Analysis:** Custom citation detection, depth ranking, n-gram overlap
- **Python:** 3.11+, managed with uv
