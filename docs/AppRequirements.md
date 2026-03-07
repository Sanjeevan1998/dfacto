# App Requirements

## 1. Executive Summary
This system is a voice-native fact-checking engine using a recursive multi-agent backend. The app features a 4-tab global navigation structure (Live Audit, Interactive, Scanner, Radar), but initial development is strictly isolated to the flagship "Live Audit" feature.

## 2. High-Level Technology Stack
* **Frontend:** Flutter SDK optimized for real-time streaming, augmented by the `ui-ux-pro-max` and `stitch` agent skills for premium, modular UI/UX design.
* **Backend:** Python FastAPI for asynchronous throughput.
* **Orchestration:** LangChain Framework for state management and agent routing.
* **Core LLM:** Gemini Live API for low-latency ASR and advanced reasoning.

## 3. Core System Data Flow (Focus: Live Audit)
* **Phase 1:** Frontend Ingestion (Flutter WebSockets streaming from the "Live Audit" tab) & Preprocessing (Agent 1 for claim extraction).
* **Phase 2:** Supervisor Orchestration (Categorization, Confidence Scoring).
* **Phase 3:** Parallel Worker Cluster (Agents 2a-2d).
* **Phase 4:** Synthesis & Output (Formatting the JSON payload for the UI's Fact-Check Cards).

## 4. Sub-Agent Orchestration
Sub-agents operate on strict, feature-specific instructions found in the `docs/` folder.

## 5. Phased Execution Roadmap
* **Step 1:** Construction of the Flutter UI shell, 4-tab global navigation, and full implementation of the flagship "Live Audit" screen with real-time WebSocket audio streaming (`docs/phase1-flutter-ui.md`).
* **Step 2:** Development of the LangChain Supervisor and worker cluster pipeline to specifically handle continuous audio streams from the Live Audit tab and perform recursive fact-checking (`docs/phase2-langchain-supervisor.md`).
* **Step 3:** Integration of Synthesis & Output mechanisms to structure the veracity assessment and format the JSON payload for the UI's Fact-Check Cards (`docs/phase3-synthesis-output.md`).
* **Step 4:** System integration, performance optimization, and rigorous end-to-end testing of the Live Audit feature.
* **Step 5:** Future expansion into the remaining tabs (Interactive, Scanner, Radar).