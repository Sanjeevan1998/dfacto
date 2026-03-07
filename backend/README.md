# Dfacto Backend

This is the backend component for the Dfacto application, an agentic web crawler built with Python and FastAPI. It orchestrates automated searches, extracts relevant headlines using LangGraph agents, and serves the data via a REST API.

## Architecture

The backend consists of several key layers:

1. **API Layer (`main.py`)**: A FastAPI application that serves as the entry point for the frontend and exposes REST endpoints.
2. **Scheduling System (`scheduler.py`)**: Uses `APScheduler` to run periodic background jobs based on configurable intervals. It manages the execution of crawler jobs and automatically triggers the fact-checking pipeline on new headlines.
3. **Database Layer (`database.py`)**: Uses SQLite (`crawler.db`) to store configuration settings (keywords, intervals) and the scraped headlines alongside their fact-check verdicts.
4. **Agent Workflow (`agents/workflow.py` & `agents/fact_checker.py`)**: 
   - **Phase 1 (Data Gathering & Distillation):** Leverages LangGraph to concurrently hit four diverse search APIs (**Tavily**, **Reddit**, **NewsAPI**, and **DuckDuckGo**). The raw output cross-section of forums, news, and web pages is passed to **Gemini 2.5 Flash** to extract clean, standardized headlines.
   - **Phase 2 (Fact-Checking Brain):** A concurrent pipeline powered by **Gemini 2.5 Flash** that takes the claims from Phase 1, targets them with new specific **Tavily/DDG** searches, and derives an internal LLM confidence ratio for each piece of evidence. It mathematically aggregates these scores to synthesize a final verdict (TRUE/FALSE/MIXED) with a source-backed explanation.

## API Endpoints

- `GET /config`: Retrieves the current crawler configuration (keywords, timer interval).
- `POST /config`: Updates the crawler configuration and reschedules the background job accordingly.
- `GET /headlines?limit=50`: Fetches the latest scraped headlines from the database.
- `POST /trigger`: Manually triggers the crawler to run immediately in the background.

## Database Schema

- **`config` table**: Stores the crawler keywords (comma-separated list) and timer interval (in minutes).
- **`headlines` table**: Stores extracted real-time data elements including the headline `title`, `source`, `url`, `snippet`, `associated_keyword`, `verdict`, `confidence_score`, `explanation`, and insertion `timestamp`.

## Environment Variables
Create a `.env` file in the `backend` directory with the following keys:
- `GEMINI_API_KEY`: Required for the Gemini 2.5 Flash fact-checking pipeline.
- `TAVILY_API_KEY`: Required for Tavily agentic search.
- `NEWSAPI_API_KEY`: Required for fetching current news.
- `REDDIT_CLIENT_ID` & `REDDIT_CLIENT_SECRET`: For fetching Reddit discussions.

## Running the Backend

Ensure you have your virtual environment set up and the necessary configurations in a `.env` file (e.g., API keys for Tavily/NewsAPI).

```bash
uvicorn main:app --reload
```
