# Phase 2: LangChain Supervisor & Recursive Worker Cluster
**Target Agent:** `fastapi-langchain-agent`
**Objective:** Build the orchestration layer and parallel worker cluster. Transition from synchronous buffer discarding to a decoupled, context-preserving asynchronous pipeline using Tavily for hyper-fast research.

## 1. Ingestion & Preprocessing Pipeline (Non-Blocking)
* **Agent 1a (Real-Time Ingestion):** Dedicated strictly to listening to the WebSocket. Pushes transcript chunks into an `asyncio.Queue` to ensure zero dropped words.
* **Agent 1b (Context & Meaning Accumulator):** Pulls from the queue to maintain a rolling "Conversational Memory Buffer." Do not discard text if no claim is found; continuously build the context window.
* **Agent 1c (Claim Gatekeeper):** Evaluates the buffer. If a claim materializes, extracts the clean claim with surrounding context and passes it to the Supervisor.

## 2. Supervisor Orchestration (The Brain)
* **Framework:** LangGraph in FastAPI.
* **Supervisor Agent:** Receives the claim, categorizes the domain, formulates specific search queries, and spins up the parallel worker cluster. Manages Depth Limits (max 3 jumps).

## 3. The Expanded Worker Cluster (Parallel Execution)
* **Agent 2a (Advanced AI Web Search):** Implement `TavilySearchResults` via LangChain. Completely remove `httpx` and `BeautifulSoup`. Use Tavily to fetch clean, LLM-ready context directly, drastically reducing latency. Pass this context to Gemini 2.0 Flash for stance classification.
* **Agent 2b (Multimodal):** Analyzes scraped text, image metadata, and video contexts.
* **Agent 2c (Social & Forums):** Queries Reddit/X to gauge public discourse.
* **Agent 2d (Trusted DBs):** Cross-references Snopes, PolitiFact, and FactCheck.org.

## 4. Synthesis & Output
* **Agent 2e (The Final Judge):** Evaluates potentially conflicting evidence from Agents 2a-2d. Weighs trust scores and determines final veracity (`TRUE`, `FALSE`, `HALF TRUE`, etc.).
* **Output:** Formats the verdict into the JSON payload and pushes it back down the WebSocket.

## 5. Verification Rules
* The pipeline must preserve context across non-claim utterances.
* Agent 2a must successfully return content using the Tavily API without making secondary HTTP/HTML scraping requests.