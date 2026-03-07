# Dfacto Backend

This is the backend component for the Dfacto application, an agentic web crawler built with Python and FastAPI. It orchestrates automated searches, extracts relevant headlines using LangGraph agents, and serves the data via a REST API.

## Architecture

The backend consists of several key layers:

1. **API Layer (`main.py`)**: A FastAPI application that serves as the entry point for the frontend and exposes REST endpoints.
2. **Scheduling System (`scheduler.py`)**: Uses `APScheduler` to run periodic background jobs based on configurable intervals. It manages the execution of crawler jobs over specified keywords.
3. **Database Layer (`database.py`)**: Uses SQLite (`crawler.db`) to store configuration settings (keywords, intervals) and the scraped headlines.
4. **Agent Workflow (`agents/workflow.py`)**: Leverages LangGraph and search APIs (Tavily, Reddit, NewsAPI) to crawl the web, fact-check, and filter relevant headlines.

## API Endpoints

- `GET /config`: Retrieves the current crawler configuration (keywords, timer interval).
- `POST /config`: Updates the crawler configuration and reschedules the background job accordingly.
- `GET /headlines?limit=50`: Fetches the latest scraped headlines from the database.
- `POST /trigger`: Manually triggers the crawler to run immediately in the background.

## Database Schema

- **`config` table**: Stores the crawler keywords (comma-separated list) and timer interval (in minutes).
- **`headlines` table**: Stores extracted real-time data elements including the headline `title`, `source`, `url`, `snippet`, `associated_keyword`, and insertion `timestamp`.

## Running the Backend

Ensure you have your virtual environment set up and the necessary configurations in a `.env` file (e.g., API keys for Tavily/NewsAPI).

```bash
uvicorn main:app --reload
```
