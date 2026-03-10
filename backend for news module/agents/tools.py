import os
import datetime

try:
    from ddgs import DDGS
except ImportError:
    from duckduckgo_search import DDGS


def search_duckduckgo_news(query: str, max_results: int = 15) -> list[dict]:
    """Search for news headlines using DuckDuckGo News tab.
    Returns list of dicts with keys: title, url, body, source, date.
    """
    try:
        with DDGS() as ddgs:
            results = list(ddgs.news(query, max_results=max_results))
        return results
    except Exception as e:
        print(f"DuckDuckGo News Error: {e}")
        return []


def search_duckduckgo_text(query: str, max_results: int = 8) -> list[dict]:
    """Search the web using DuckDuckGo text search.
    Returns list of dicts with keys: title, href, body.
    """
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        return results
    except Exception as e:
        print(f"DuckDuckGo Text Error: {e}")
        return []


def search_tavily(query: str) -> str:
    """Optional: Search using Tavily API for richer results (requires TAVILY_API_KEY)."""
    api_key = os.environ.get("TAVILY_API_KEY")
    if not api_key or api_key == "your_tavily_api_key_here":
        return "Tavily Search: API key not provided."
    try:
        from tavily import TavilyClient
        client = TavilyClient(api_key=api_key)
        response = client.search(query=query, search_depth="advanced", max_results=5)
        results_str = ""
        for result in response.get("results", []):
            results_str += f"Title: {result.get('title')}\nURL: {result.get('url')}\nContent: {result.get('content')}\n\n"
        return results_str
    except Exception as e:
        return f"Tavily Error: {e}"
