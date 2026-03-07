# Phase 3: The Final Judge, Synthesis & Output
**Target Agent:** `fastapi-langchain-agent`
**Objective:** Implement the terminal LangGraph nodes (Agent 2e and the Output Agent) to consolidate worker data, judge veracity, and dispatch the JSON payload to the Flutter client.

## 1. Data Aggregation & Trust Weighting
* **Summary Aggregation Node:** Await the completion of the Phase 2 Worker Cluster. Merge all findings into a unified context block.
* **Trust Weighting:** Assign higher priority/weight to evidence gathered from Agent 2d (Trusted DBs like Snopes) over general web results gathered by Agent 2a (Tavily).

## 2. Veracity Assessment (Agent 2e: The Final Judge)
* **Synthesis Node:** Evaluate the weighted context against the original "Core Claim".
* Strictly assign one of the following enumerations: `TRUE`, `MOSTLY TRUE`, `HALF TRUE`, `MOSTLY FALSE`, `FALSE`, or `UNVERIFIABLE`.
* **Conclusion Node:** Generate a concise, human-readable justification (1-2 sentences) explaining exactly why the claim received its specific rating. Extract the highest-weight URLs to cite as sources.

## 3. Payload Formatting & WebSocket Dispatch
* **Output Agent:** Construct a strict JSON payload.
* Schema required: `{ "claim_veracity": "STRING", "summary_and_explanation": "STRING", "key_sources": ["URL_1", "URL_2"] }`.
* **Dispatch:** Push this JSON payload into the outbound WebSocket queue so it instantly renders as a "Fact-Check Card" on the Flutter UI.

## 4. Verification Rules
* The system must strictly output the JSON schema without Markdown code-block formatting (no ` ```json ` tags), ensuring immediate parsing by the Dart client.
* The system must successfully execute an end-to-end test: Ingesting audio -> LangGraph processing -> JSON dispatch back to Flutter.