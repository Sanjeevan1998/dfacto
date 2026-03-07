# Phase 1: Global Navigation & Live Audit UI
**Target Agent:** `flutter-ui-agent`
**Objective:** Scaffold the Flutter app, implement the 4-tab bottom navigation shell, and fully build the "Live Audit" UI using premium UX skills.

## 1. Required Agent Skills
Before writing UI code, you MUST apply principles from:
* **UI UX Pro Max (`nextlevelbuilder/ui-ux-pro-max-skill`):** Establish a premium Design System (dark mode preferred for a "Studio" feel), high-contrast typography, and fluid micro-interactions.
* **Stitch (`google-labs-code/stitch-skills`):** Ensure widget composition is highly modular and cleanly separated.

## 2. Micro-Tasks
* **2.1 Global Navigation Shell:** Create a `BottomNavigationBar` with 4 tabs: "Live Audit", "Interactive", "Scanner", and "Radar".
* **2.2 Tab Stubs (Interactive, Scanner, Radar):** Create clean, branded placeholder screens for these 3 tabs containing simple "Coming Soon" typography. Do not build logic for them.
* **2.3 Live Audit UI (Active Screen):** Build the flagship studio monitor screen:
    * **Top Half:** A prominent "Start Listening" button accompanied by a fluid audio visualizer (waveform animation) indicating a hot mic.
    * **Bottom Half:** A scrolling timeline `ListView`.
    * **Components:** Design a sleek "Fact-Check Card" that will slide in next to transcribed sentences. It must support a confidence score badge (e.g., TRUE/FALSE), a one-sentence summary, and a source hyperlink.
* **2.4 WebSocket & Audio Client:** Implement background microphone access (`Info.plist` / `AndroidManifest.xml`). Stream audio chunks from the "Live Audit" screen to the FastAPI WebSocket.

## 3. Verification Rules
* The app must compile natively without UI overflow errors.
* Navigation between the 4 tabs must be smooth, displaying the correct stubs.
* The Live Audit screen must successfully trigger the mic permission and animate the waveform.