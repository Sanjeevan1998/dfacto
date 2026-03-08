import os
from typing import TypedDict, List
from langgraph.graph import StateGraph, END
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage
import json
import concurrent.futures

from agents.tools import search_internet, search_newsapi, search_reddit, search_tavily

class GraphState(TypedDict):
    keywords: str
    search_results: str
    headlines: List[dict]

def search_node(state: GraphState):
    """
    Crawls the internet based on the keywords using multiple sources.
    """
    keywords = state["keywords"]
    print(f"--> Searching multiple sources for: {keywords}")
    
    # We will search concurrently
    results_str = ""
    
    with concurrent.futures.ThreadPoolExecutor() as executor:
        future_newsapi = executor.submit(search_newsapi, keywords)
        future_reddit = executor.submit(search_reddit, keywords)
        
        # For DDG and Tavily, we often want conversational/trending queries
        query = f"latest trending news headlines {keywords}"
        future_tavily = executor.submit(search_tavily, query)
        future_ddg = executor.submit(search_internet, query)
        
        newsapi_res = future_newsapi.result()
        reddit_res = future_reddit.result()
        tavily_res = future_tavily.result()
        ddg_res = future_ddg.result()
        
    results_str += "=== NEWSAPI RESULTS ===\n" + newsapi_res + "\n"
    results_str += "=== REDDIT RESULTS ===\n" + reddit_res + "\n"
    results_str += "=== TAVILY RESULTS ===\n" + tavily_res + "\n"
    results_str += "=== DUCKDUCKGO RESULTS ===\n" + ddg_res + "\n"
    
    print("--> Finished collecting context from all sources.")
    return {"search_results": results_str}

def extract_node(state: GraphState):
    """
    Extracts relevant headlines from the search results using Gemini.
    """
    search_results = state["search_results"]
    print("--> Extracting headlines from search results...")
    
    # Initialize Gemini model
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key or api_key == "your_gemini_api_key_here":
        print("WARNING: GEMINI_API_KEY is not set or invalid.")
        return {"headlines": []}
        
    llm = ChatGoogleGenerativeAI(model="gemini-2.5-pro", google_api_key=api_key, temperature=0.1)
    
    keywords = state["keywords"]
    
    system_prompt = f"""
    You are an expert news aggregator and strict fact-checker. 
    Your task is to extract the most important and trending headlines 
    from the provided raw search context (which includes NewsAPI, Reddit, Tavily, and DuckDuckGo data).
    
    CRITICAL INSTRUCTION: You MUST ONLY extract headlines that are strictly relevant to the following keywords/phrases: "{keywords}".
    If a headline or article snippet does not clearly relate to these keywords, DO NOT include it in your output.
    Quality over quantity. It is better to return an empty array than to include irrelevant information.
    
    Return the result EXACTLY as a valid JSON array of objects, with no markdown formatting or backticks.
    Each object must have the following keys:
    - title (string)
    - source (string) - Be specific, e.g., "r/technology" or "TechCrunch (via NewsAPI)" or "Tavily"
    - url (string)
    - snippet (string)
    
    If you cannot find specific information for source or url, provide a best guess based on context or leave empty string.
    DO NOT return anything else besides the JSON array.
    """
    
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=f"Raw Search Context:\n{search_results}")
    ]
    
    response = llm.invoke(messages)
    
    try:
        # Very simple JSON parsing
        content = response.content.strip()
        if content.startswith("```json"):
            content = content[7:]
        if content.endswith("```"):
            content = content[:-3]
        headlines = json.loads(content.strip())
        if not isinstance(headlines, list):
            headlines = []
    except Exception as e:
        print(f"Error parsing Gemini response: {e}")
        # Try finding json array manually if standard parsing fails
        import re
        match = re.search(r'\[.*\]', response.content.strip(), re.DOTALL)
        if match:
             try:
                 headlines = json.loads(match.group(0))
             except:
                 headlines = []
        else:
             headlines = []
        
    return {"headlines": headlines}


# Build LangGraph
workflow = StateGraph(GraphState)
workflow.add_node("search", search_node)
workflow.add_node("extract", extract_node)

workflow.set_entry_point("search")
workflow.add_edge("search", "extract")
workflow.add_edge("extract", END)

app = workflow.compile()

def run_crawler(keywords: str) -> List[dict]:
    """Execute the agentic crawler workflow."""
    final_state = app.invoke({"keywords": keywords, "search_results": "", "headlines": []})
    return final_state["headlines"]
