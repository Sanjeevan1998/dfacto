# Phase 3: Synthesis, Veracity Assessment & Output
**Target Agent:** `fastapi-langchain-agent`
**Objective:** Consolidate the asynchronous worker data into a final, deterministic assessment payload for the Flutter client.

## 1. Data Aggregation
* **Summary Aggregation Agent:** Await the completion or timeout of the Phase 2 Worker Cluster branches. Merge all textual findings and source links into a unified context block.

## 2. Veracity Assessment
* **Synthesis Agent:** Evaluate the unified context against the original "Core Claim".
* Strictly assign one of the following enumerations: `TRUE`, `MOSTLY TRUE`, `HALF TRUE`, `MOSTLY FALSE`, `FALSE`, or `UNVERIFIABLE`.
* **Conclusion Agent:** Generate a concise, human-readable justification explaining exactly why the claim received its specific rating.

## 3. Payload Formatting & Dispatch
* **Output Agent:** Construct a strict JSON payload.
* Schema required: `{ "claim_veracity": "STRING", "summary_and_explanation": "STRING", "key_sources": ["URL_1", "URL_2"] }`.
* Dispatch this JSON payload back down the active WebSocket connection to the Flutter client.

## 4. Verification Rules
* The pipeline must successfully process a mock aggregated context block.
* The system must strictly output the JSON schema without Markdown code-block formatting attached, ensuring immediate parsing by the Dart client.