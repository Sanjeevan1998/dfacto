# Dfacto Backend

The Dfacto backend is a Python-based intelligent agentic crawler and fact-checking engine built with FastAPI, LangGraph, and Playwright. It autonomously browses the web to extract news, assess claims, and save verifiable facts.

## High-Level Architecture & Design

The backend acts as an autonomous data pipeline. It operates on a scheduled loop, picking up configured keywords, searching the open web for them using an AI-driven browser, extracting meaningful headlines, and running a rigorous claim-verification LangGraph on each headline.

This architecture can be visualized in two distinct workflows: the **Crawler Workflow** and the **Fact-Checker Workflow**.

### 1. Crawler Workflow (Data Acquisition)

The Crawler Workflow (`agents/workflow.py`) is responsible for scouring the web for a specific query and returning unique, trending headlines.

- **Node 1: `search`**: Uses the `agentic_browser_search` tool (powered by `browser-use` and Playwright). A headless browser navigated by Gemini 2.5 Flash autonomously searches duckduckgo/google, opens links, reads content, and returns raw text context about the given `keywords`.
- **Node 2: `extract`**: Passes the raw context to a Gemini 2.5 Pro LLM. The LLM acts as an expert news aggregator with a strict instruction to apply a **Uniqueness Filter**. It extracts distinct factual headlines into a structured JSON array (Title, Source, URL, Snippet), explicitly filtering out duplicates of the same event.

### 2. Fact-Checker Workflow (Verification)

Once the Crawler returns a list of headlines, each headline is individually passed through the Fact-Checker Workflow (`agents/fact_checker.py`), another LangGraph pipeline.

- **Pre-check: `classify_claim`**: A fast filter that ensures the text actually contains a verifiable factual claim before invoking the full pipeline.
- **Node 1: `extract`**: Identifies the single most verifiable `core_claim` from the headline snippet.
- **Node 2: `categorize`**: Tags the claim into predefined categories (political, scientific, economic, other).
- **Node 3: `fan_out`**: Uses the `agentic_browser_search` tool again, this time optimized for fact-checking. The browser agent autonomously browses the web searching for evidence *about* the extracted claim (excluding the original source URL to prevent bias). It returns raw evidence context, which is then parsed by Gemini into multiple `EvidenceItem` objects containing a `stance` (support, contradict, neutral) and a `trust_weight`.
- **Node 4: `aggregate`**: Takes all collected `EvidenceItem` objects and calculates an aggregated confidence score. It normalizes weights to produce a score between 0.0 and 1.0. 
  - `> 0.70` -> **TRUE**
  - `< 0.30` -> **FALSE**
  - Otherwise -> **MIXED**
- **Conditional Edge**: If the confidence score sits in the gray zone (0.3 to 0.7) and max depth isn't reached, it loops back to `fan_out` to dig deeper. Otherwise, it proceeds to synthesize.
- **Node 5: `synthesize`**: Based on the gathered evidence and the final verdict, a LLM generates a single-sentence concise explanation of *why* the claim received its verdict, considering the temporal context of the current system time.

### System Components

- **`main.py`**: A FastAPI application that exposes REST endpoints (`/config`, `/headlines`, `/trigger`) for the frontend to consume. 
- **`scheduler.py`**: Uses `APScheduler` to run a background job at a customizable interval (e.g., every 60 minutes). It triggers the Crawler Workflow and subsequently the Fact-Checker Workflow on the newly discovered data.
- **`database.py`**: Manages a local SQLite database (`crawler.db`). It stores the user's target phrases, schedule intervals, and the fully processed headlines (`id`, `title`, `source`, `snippet`, `verdict`, `confidence_score`, `explanation`, `timestamp`).
- **`agents/tools.py`**: Contains the `agentic_browser_search` engine powered by the `browser-use` library (`Agent`, `Browser`, `ChatGoogle`).

### Environment Variables Required

Ensure an `.env` file is placed in this directory with:
- `GEMINI_API_KEY`: Required for LLM steps and the autonomous browser agent.

### Setup and Running

1. Create a virtual environment: `python3 -m venv venv`
2. Activate and install dependencies: `source venv/bin/activate && pip install -r requirements.txt`
3. Run the FastAPI server: `uvicorn main:app --reload --port 8000`
