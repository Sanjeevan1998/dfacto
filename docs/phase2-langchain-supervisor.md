# Phase 2: LangChain Supervisor (Live Audit Pipeline)
**Target Agent:** `fastapi-langchain-agent`
**Objective:** Build the Phase 2 orchestration layer and Phase 3 worker cluster specifically to handle the continuous audio stream from the "Live Audit" tab.

## 1. Supervisor Orchestration
* **Framework:** LangGraph / LangChain in FastAPI.
* **Agent 1 (Extraction):** Intercept the WebSocket audio stream from the Flutter Live Audit screen. Transcribe via Gemini Live and isolate the "Core Claim".
* **Supervisor Agent:** Route the claim based on category. Implement a control loop governed by: Confidence Score Gauge, Depth Limit (max 3 jumps), and a deterministic Stop Condition.

## 2. The Worker Cluster (Fact-Checking)
* **Agent 2a (Web/News):** Spin up parallel sub-agents to search and scrape top web results simultaneously for the extracted claim.
* **Agent 2d (Trusted DBs):** Cross-reference Snopes and PolitiFact.

## 3. Recursive Feedback Loop
* Workers return data with a local confidence metric.
* If the Supervisor deems aggregated confidence too low (and Depth Limit not reached), it triggers a recursive deep search with refined queries.

## 4. Verification Rules
* The Supervisor graph must compile without cyclical deadlocks.
* A dummy audio stream from the Flutter UI must successfully traverse the LangChain graph and trigger the parallel workers.