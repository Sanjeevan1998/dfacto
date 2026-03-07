# Dfacto

**Status**: Work in Progress (WIP)

Currently in development, Dfacto aims to provide comprehensive, real-time fact-checking across various modalities. The application is designed to support four core features:

1. **Live Conversation Fact-Checking**: Auditing live audio (e.g., debates, interviews) to fact-check statements in real-time with proper sources.
2. **Media & Link Verification**: Analyzing shared images, videos, and URLs to verify the authenticity of the contents.
3. **Interactive Mode**: A conversational interface where users can chat with the app to get help fact-checking specific claims.
4. **Agentic News Crawler**: Continuously monitoring the web for live, factual news based on user-preset keywords and schedules (currently implemented).

## Architecture & Logic

The application logic is fundamentally split into two distinct phases across all features:
- **Phase 1 (Data Gathering & Distillation)**: Specialized modules that collect data depending on the feature. For the active Agentic Crawler, this phase concurrently scrapes data from **Reddit** (praw), **NewsAPI**, **Tavily** (AI semantic search), and **DuckDuckGo**. The raw, noisy text from these varied sources is passed through **Gemini 2.5 Flash** (via LangGraph) to distill a clean list of highly relevant, canonical headlines.
- **Phase 2 (The Fact-Checker Brain)**: A central, concurrent pipeline powered by LangGraph and **Gemini 2.5 Flash**. It receives the distilled headlines from Phase 1 and performs a multi-step evaluation:
  1. **Extraction**: Gemini extracts the core, verifiable claim from the headline.
  2. **Evidence Gathering**: The system concurrently queries **Tavily** and **DuckDuckGo** for evidence specifically targeting the extracted claim.
  3. **Confidence Scoring**: Gemini evaluates the evidence, assigning a stance (support/contradict) and a dynamic `llm_confidence` score based on the source text's factuality. 
  4. **Synthesis**: The individual scores are mathematically aggregated against the search engines' baseline trust weights to produce a final quantitative confidence percentage and a qualitative verdict (TRUE, FALSE, MIXED) with a brief paragraph explanation.

## Project Structure

The repository is a monorepo divided into two main components:

- **`backend/`**: A Python FastAPI application that currently implements the Agentic News Crawler (Phase 1) and the core Fact-Checker Brain (Phase 2). Results are stored in a SQLite database.
- **`frontend/`**: A cross-platform Flutter application (mobile/web) designed to interface with the backend and display the fact-checking verdicts dynamically.

## Getting Started

*(Instructions on how to run both the backend and frontend will be added here as the project progresses).*
