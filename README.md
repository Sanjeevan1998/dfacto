# Dfacto: Agentic News Crawler & Fact-Checker

Dfacto is a Next-Generation AI Agent pipeline that proactively scours the web for trending information and rigorously fact-checks claims using advanced Multi-Modal Browser Agents and LLM-driven LangGraph workflows. 

Rather than relying on outdated static APIs, Dfacto utilizes a Playwright-driven headless browser powered by Google's Gemini 2.5 Flash to visually inspect, read, and extract data from the live internet exactly as a human would.

## Project Layout

The repository is cleanly divided into a backend agentic engine and a frontend display application.

- **`/backend` (Python / FastAPI / LangGraph / Playwright)**
  The brain of the system. It consists of multiple orchestrated LLM workflows. It runs on a scheduled interval to crawl the internet for specified phrases, extract unique claims, actively browse the internet *again* to find contradictory or supporting evidence, and aggregate a final fact-checking verdict and explanation.
  *(See `backend/README.md` for a highly detailed flow chart breakdown of the architectural design).*

- **`/frontend` (Flutter Web Application)**
  A sleek, cross-platform interface allowing users to configure the backend crawler's target keywords and intervals. It cleanly presents the extracted headlines alongside their categorical fact-check verdicts (TRUE, FALSE, MIXED) using aesthetic Material 3 components.
  *(See `frontend/README.md` for details on the Flutter widget tree and API connections).*

## Getting Started Overview

To run Dfacto locally, you will need to simultaneously run the backend server and the frontend application.

1. Ensure you have an active `GEMINI_API_KEY` saved in `backend/.env`.
2. Boot up the backend using Python (`uvicorn main:app --port 8000`).
3. Boot up the frontend using Flutter (`flutter run -d chrome`).

See the individual directory READMEs for deeper setup instructions and architecture details.
