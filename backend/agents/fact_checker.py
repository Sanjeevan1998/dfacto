import os
import json
import concurrent.futures
import datetime
from typing import TypedDict, List, Optional
from langgraph.graph import StateGraph, END
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage
from pydantic import BaseModel, Field

from agents.tools import agentic_browser_search
import time
import asyncio

def llm_invoke_with_retry(llm, messages, max_retries=3):
    for attempt in range(max_retries):
        try:
            return llm.invoke(messages)
        except Exception as e:
            if "429" in str(e) or "Resource exhaustion" in str(e).lower() or "quota" in str(e).lower():
                if attempt < max_retries - 1:
                    sleep_time = (2 ** attempt) * 2
                    print(f"Quota exhausted. Retrying in {sleep_time} seconds...")
                    time.sleep(sleep_time)
                else:
                    raise e
            else:
                raise e

class EvidenceItem(BaseModel):
    source: str
    url: str
    snippet: str
    stance: str  # support, contradict, neutral
    trust_weight: float
    llm_confidence: float = 1.0

class GraphState(TypedDict):
    transcript: str
    source_url: Optional[str]
    core_claim: Optional[str]
    category: Optional[str]
    depth: int
    worker_results: List[EvidenceItem]
    confidence: float
    verdict: Optional[str]
    summary: Optional[str]

def classify_claim(text: str) -> bool:
    """
    Fast pre-check to determine if the text contains a verifiable claim.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key or api_key == "your_gemini_api_key_here":
        return True # Fallback to running pipeline if missing key
        
    llm = ChatGoogleGenerativeAI(model="gemini-2.5-pro", google_api_key=api_key, temperature=0.0)
    prompt = f"Does the following text contain a factual claim that can be verified and evaluated as true or false? Answer YES or NO.\nText: {text}"
    try:
        response = llm_invoke_with_retry(llm, [HumanMessage(content=prompt)])
        content = response.content.strip().upper()
        return "YES" in content
    except Exception:
        return True

def extract_node(state: GraphState):
    print("FactChecker -> Extracting core claim...")
    transcript = state["transcript"]
    
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key or api_key == "your_gemini_api_key_here":
        return {"core_claim": transcript}
        
    llm = ChatGoogleGenerativeAI(model="gemini-2.5-pro", google_api_key=api_key, temperature=0.1)
    
    prompt = """
    Extract the single most verifiable core claim from the transcript. 
    Return EXACTLY as JSON: {"transcript": "...", "core_claim": "..."}
    Do not use markdown blocks.
    """
    messages = [
        SystemMessage(content=prompt),
        HumanMessage(content=transcript)
    ]
    try:
        response = llm_invoke_with_retry(llm, messages)
        res_content = response.content.strip()
    except Exception as e:
        print(f"Error extracting claim: {e}")
        return {"core_claim": transcript}
    
    try:
        content = response.content.strip()
        if content.startswith("```json"):
            content = content[7:]
        if content.endswith("```"):
            content = content[:-3]
        data = json.loads(content.strip())
        claim = data.get("core_claim", transcript)
    except:
        claim = transcript
        
    return {"core_claim": claim}

def categorize_node(state: GraphState):
    print("FactChecker -> Categorizing claim...")
    claim = state.get("core_claim") or state["transcript"]
    
    claim_lower = claim.lower()
    if any(k in claim_lower for k in ["election", "president", "policy", "law", "government"]):
        cat = "political"
    elif any(k in claim_lower for k in ["virus", "climate", "space", "study", "research"]):
        cat = "scientific"
    elif any(k in claim_lower for k in ["economy", "stock", "tax", "inflation", "market"]):
        cat = "economic"
    else:
        cat = "other"
        
    return {"category": cat}
    
def _extract_evidence_items(claim: str, search_result: str) -> List[EvidenceItem]:
    """Helper to parse out evidence from the browser search string."""
    if not search_result or search_result.strip() == "":
        return []
        
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key or api_key == "your_gemini_api_key_here":
        return [EvidenceItem(
            source="Browser Agent",
            url="",
            snippet="Skipped evaluation (No API Key).",
            stance="neutral",
            trust_weight=0.0
        )]
        
    llm = ChatGoogleGenerativeAI(model="gemini-2.5-pro", google_api_key=api_key, temperature=0.1)
    
    safe_search_result = search_result.strip()
    if not safe_search_result:
        safe_search_result = "No evidence found."
        
    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    prompt_str = f"""You are a strict fact checking assistant. 
Current System Time: {current_time}
You are evaluating whether the given textual evidence supports or contradicts the claim.
CRITICAL TEMPORAL INSTRUCTION: Use the Current System Time to determine if an event in the evidence is in the past, present, or future. If the evidence describes a speculative or future event relative to the Current System Time, it CANNOT support a claim that the event actually happened.

Return EXACTLY as a JSON array of objects with no markdown blocks. 
Each object must have:
- 'stance' (support/contradict/neutral)
- 'snippet' (a short quote from the text supporting the stance)
- 'url' (if available in the text)
- 'llm_confidence' (a float between 0.0 and 1.0 representing how sure you are of the stance based on the text)"""

    messages = [
        SystemMessage(content=prompt_str),
        HumanMessage(content=f"Claim: {claim}\nEvidence: {safe_search_result}")
    ]
    try:
        response = llm_invoke_with_retry(llm, messages)
        content = response.content.strip()
        if content.startswith("```json"): content = content[7:]
        if content.endswith("```"): content = content[:-3]
        data_list = json.loads(content.strip())
        
        if isinstance(data_list, dict) and "stance" in data_list:
            data_list = [data_list]
            
        items = []
        for data in data_list:
            conf = data.get("llm_confidence", 1.0)
            try:
                conf = float(conf)
                if conf > 1.0: conf = conf / 100.0
            except:
                conf = 1.0
                
            items.append(EvidenceItem(
                source="Browser Agent Search",
                url=data.get("url", "") or "",
                snippet=data.get("snippet", "") or "",
                stance=data.get("stance", "neutral") or "neutral",
                trust_weight=1.0,
                llm_confidence=conf
            ))
        return items
    except Exception as e:
        print(f"Error evaluating evidence: {e}")
        return []

def fan_out_node(state: GraphState):
    print("FactChecker -> Searching for evidence via Agentic Browser...")
    claim = state.get("core_claim", state["transcript"])
    depth = state.get("depth", 0)
    source_url = state.get("source_url")
    existing_evidence = state.get("worker_results", [])
    
    query = claim
    headless_env = os.environ.get("HEADLESS_BROWSER", "True").lower() == "true"
    
    try:
        browser_res = asyncio.run(agentic_browser_search(query, task_type="fact_check", exclude_url=source_url, headless=headless_env))
    except Exception as e:
        print(f"Browser Agent Exception: {e}")
        browser_res = ""
        
    new_evidence = _extract_evidence_items(claim, browser_res)
        
    return {
        "worker_results": existing_evidence + new_evidence,
        "depth": depth + 1
    }

def aggregate_node(state: GraphState):
    print("FactChecker -> Aggregating confidence...")
    evidence = state.get("worker_results", [])
    
    if not evidence:
        return {"confidence": 0.5, "verdict": "UNKNOWN"}
        
    total_weight = 0.0
    support_score = 0.0
    
    for item in evidence:
        # Dynamically adjust the base trust weight of the source by how confident the LLM was in its reading
        true_weight = item.trust_weight * item.llm_confidence
        total_weight += true_weight
        
        if item.stance == "support":
            support_score += true_weight
        elif item.stance == "contradict":
            support_score -= true_weight
            
    # Normalize between 0 and 1
    # max possible score = total_weight, min possible = -total_weight
    # shift range to 0 to 2*total_weight, then div by 2*total_weight
    if total_weight > 0:
        normalized = (support_score + total_weight) / (2 * total_weight)
    else:
        normalized = 0.5
        
    if normalized >= 0.70:
        verdict = "TRUE"
    elif normalized <= 0.30:
        verdict = "FALSE"
    else:
        verdict = "MIXED"
        
    return {"confidence": normalized, "verdict": verdict}

def should_continue(state: GraphState) -> str:
    conf = state.get("confidence", 0.5)
    depth = state.get("depth", 0)
    
    # If confidence is in the gray zone and we haven't dug deep enough, search more
    if 0.30 < conf < 0.70 and depth < 3:
        return "fan_out"
    return "synthesize"

def synthesize_node(state: GraphState):
    print("FactChecker -> Synthesizing final result...")
    claim = state.get("core_claim", state["transcript"])
    verdict = state.get("verdict", "UNKNOWN")
    evidence = state.get("worker_results", [])
    
    snippets = "\n".join([f"{e.source} ({e.stance}): {e.snippet}" for e in evidence])
    
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key or api_key == "your_gemini_api_key_here" or not evidence:
        return {"summary": "Insufficient data (or invalid API Key) to synthesize an explanation."}
        
    llm = ChatGoogleGenerativeAI(model="gemini-2.5-pro", google_api_key=api_key, temperature=0.1)
    
    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    prompt = f"""
    Current System Time: {current_time}
    Fact Check Result: {verdict}
    Claim: {claim}
    Evidence:
    {snippets}
    
    Write a single-sentence concise explanation for WHY this claim is {verdict} based on the evidence. Ensure you reference temporal context accurately based on the Current System Time.
    """
    try:
        response = llm_invoke_with_retry(llm, [HumanMessage(content=prompt)])
        summary = response.content.strip()
    except Exception as e:
        print(f"Error synthesizing: {e}")
        summary = "Error generating summary."
        
    return {"summary": summary}

# Build LangGraph
workflow = StateGraph(GraphState)

workflow.add_node("extract", extract_node)
workflow.add_node("categorize", categorize_node)
workflow.add_node("fan_out", fan_out_node)
workflow.add_node("aggregate", aggregate_node)
workflow.add_node("synthesize", synthesize_node)

workflow.set_entry_point("extract")
workflow.add_edge("extract", "categorize")
workflow.add_edge("categorize", "fan_out")
workflow.add_edge("fan_out", "aggregate")
workflow.add_conditional_edges("aggregate", should_continue)
workflow.add_edge("synthesize", END)

fact_check_app = workflow.compile()

def run_fact_checker(text: str, source_url: str = None) -> dict:
    """Entry point to run the fact checking pipeline on a text snippet."""
    
    if not classify_claim(text):
        print("FactChecker -> No verifiable claim found. Short-circuiting.")
        return {
            "verdict": "N/A",
            "confidence": 0.0,
            "explanation": "No verifiable claim detected in text."
        }
    
    initial_state = {
        "transcript": text,
        "source_url": source_url,
        "core_claim": None,
        "category": None,
        "depth": 0,
        "worker_results": [],
        "confidence": 0.5,
        "verdict": None,
        "summary": None
    }
    
    final_state = fact_check_app.invoke(initial_state)
    
    return {
        "verdict": final_state.get("verdict", "UNKNOWN"),
        "confidence": final_state.get("confidence", 0.5),
        "explanation": final_state.get("summary", "")
    }
