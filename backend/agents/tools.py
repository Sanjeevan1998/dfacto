import os
import asyncio
import datetime
from langchain_community.tools import DuckDuckGoSearchRun
from browser_use import Agent, Browser, ChatGoogle

async def agentic_browser_search(query: str, task_type: str = 'general', exclude_url: str | None = None, headless: bool = True) -> str:
    """Search the internet autonomously using a multi-modal browser agent."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key or api_key == "your_gemini_api_key_here":
        return "Agentic Browser Search: API key not provided."
        
    llm = ChatGoogle(model="gemini-2.5-pro", api_key=api_key)
    
    browser = Browser(headless=headless)
    
    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    task_instructions = f"Current System Time: {current_time}. Search the web for the following query: '{query}'. "
    
    if task_type == 'fact_check':
        task_instructions += (
            "This is a careful fact-checking data gathering task. "
            "STEP 1: Find at max 2 articles related to this query to understand the context and establish a 'meaningful headline'. "
            "STEP 2: Use this exact headline to gather evidence by searching for it directly (do NOT write 'fact check' in the search box). "
            "STEP 3: Extract the headlines, publication dates, and full text of the articles you find. "
            "STEP 4: IMPORTANT: Do NOT attempt to output a true/false verdict or judge the claim yourself. Your ONLY job is to gather and return the raw textual evidence so that a downstream LLM can make the final logical decision."
        )
        
    if exclude_url:
        task_instructions += f"CRITICAL: Do NOT click on or extract data from this exact domain/URL: {exclude_url}. "
        
    task_instructions += '''
    CRITICAL RULES to prevent infinite loops:
    1. Maximum Depth: Click into a maximum of 3-5 links. Immediately close tabs after reading to prevent memory crashes.
    2. Popup Handling: Use the browser `go_back` or equivalent action if you encounter an unclosable popup, cookie banner, or paywall.
    
    Gather comprehensive context, headlines, snippets, and source URLs. 
    Return a detailed summary of your findings including the original sources.
    '''
    
    try:
        agent = Agent(task=task_instructions, llm=llm, browser=browser)
        result = await agent.run()
        
        # Ensure we return a complete string summary
        final_text = ""
        if hasattr(result, 'final_result') and result.final_result():
            final_text = result.final_result()
        elif hasattr(result, 'history') and result.history:
            # Fallback if no clean final result
            final_text = "\n".join([str(h.result) for h in result.history if h.result])
        else:
            final_text = str(result)
            
        return final_text if final_text else "No relevant context extracted."
    except Exception as e:
        return f"Browser Agent Error: {e}"
    finally:
        await browser.stop()

def search_internet(query: str) -> str:
    """Search the internet using DuckDuckGo."""
    try:
        search = DuckDuckGoSearchRun()
        return search.invoke(query)
    except Exception as e:
        return f"DuckDuckGo Error: {e}"

def search_tavily(query: str) -> str:
    """Search the internet using Tavily API for better agentic context."""
    api_key = os.environ.get("TAVILY_API_KEY")
    if not api_key or api_key == "your_tavily_api_key_here":
        return "Tavily Search: API key not provided."
    
    try:
        client = TavilyClient(api_key=api_key)
        response = client.search(query=query, search_depth="advanced", max_results=5)
        # Format results into a string
        results_str = ""
        for result in response.get("results", []):
            results_str += f"Title: {result.get('title')}\nURL: {result.get('url')}\nContent: {result.get('content')}\n\n"
        return results_str
    except Exception as e:
        return f"Tavily Error: {e}"

def search_newsapi(query: str) -> str:
    """Fetch top headlines and relevant news using NewsAPI."""
    api_key = os.environ.get("NEWSAPI_API_KEY")
    if not api_key or api_key == "your_newsapi_key_here":
        return "NewsAPI: API key not provided."
        
    try:
        newsapi = NewsApiClient(api_key=api_key)
        # Replacing commas with OR for NewsAPI q parameter
        q_param = " OR ".join([k.strip() for k in query.split(",") if k.strip()])
        if not q_param:
             q_param = query

        all_articles = newsapi.get_everything(q=q_param, language='en', sort_by='relevancy', page_size=10)
        
        results_str = ""
        for article in all_articles.get('articles', []):
            title = article.get('title', 'No Title')
            source = article.get('source', {}).get('name', 'Unknown Source')
            desc = article.get('description', '')
            url = article.get('url', '')
            results_str += f"Title: {title}\nSource: {source}\nURL: {url}\nDescription: {desc}\n\n"
            
        return results_str
    except Exception as e:
        return f"NewsAPI Error: {e}"

def search_reddit(query: str) -> str:
    """Fetch hot posts from Reddit matching the query."""
    client_id = os.environ.get("REDDIT_CLIENT_ID")
    client_secret = os.environ.get("REDDIT_CLIENT_SECRET")
    user_agent = os.environ.get("REDDIT_USER_AGENT", "dfacto_crawler:v1.0")
    
    if not client_id or client_id == "your_reddit_client_id_here" or not client_secret or client_secret == "your_reddit_client_secret_here":
        return "Reddit: Client credentials not provided."
        
    try:
        reddit = praw.Reddit(
            client_id=client_id,
            client_secret=client_secret,
            user_agent=user_agent
        )
        
        results_str = ""
        for submission in reddit.subreddit("all").search(query, sort="hot", limit=10):
            results_str += f"Score: {submission.score} | Subreddit: r/{submission.subreddit}\n"
            results_str += f"Title: {submission.title}\nURL: {submission.url}\n"
            # Get snippet of text if it exists
            if submission.selftext:
                results_str += f"Content Snippet: {submission.selftext[:200]}...\n"
            results_str += "\n"
            
        return results_str
    except Exception as e:
        return f"Reddit Error: {e}"
