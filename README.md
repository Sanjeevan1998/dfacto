# Dfacto

**Team Name:** Facters
**Team Members:** Erin Kong, Arnab Bhowal, Nasir Hasan Dilawar, and Sanjeevan Adhikari

Dfacto is a real-time AI fact-checking app with four core features:

1. **Live Audit** — Real-time fact-checking of live audio (debates, interviews) with sources
2. **Interactive** — Conversational fact-checking interface *(coming soon)*
3. **Scanner** — Media & link verification *(coming soon)*
4. **News** — Agentic news crawler that continuously monitors the web based on keywords and fact-checks each headline

---

## Architecture

```
dfacto_app/          → Flutter mobile app (Android/iOS)
dfacto_backend/      → Live Audit backend (FastAPI + WebSocket, port 8000)
backend for news module/  → News Crawler backend (FastAPI + REST, port 8001)
```

Both backends run on your **Mac**. Your **phone** connects to them over the local Wi-Fi network.

---

## Prerequisites

### Mac (backend)
- Python 3.11+
- A virtual environment for each backend (see setup below)
- `GEMINI_API_KEY` — get one free at [aistudio.google.com](https://aistudio.google.com)

### Phone (Flutter app)
- Android phone with USB debugging enabled, or iOS with dev profile
- On the **same Wi-Fi network** as your Mac
- Android: `adb` connected via USB or Wi-Fi

### Mac (Flutter)
- Flutter SDK installed and on PATH (`flutter --version` should work)
- Android SDK / Xcode as appropriate

---

## Step 1 — Find Your Mac's Local IP Address

Your phone connects to your Mac's IP. Run this in Terminal:

```bash
ipconfig getifaddr en0
# Example output: 192.168.1.158
```

> If you're on Ethernet instead of Wi-Fi, try `en1` or check System Settings → Network.

---

## Step 2 — Update the IP in the Flutter App

Open [dfacto_app/lib/core/config/api_config.dart](dfacto_app/lib/core/config/api_config.dart) and replace the IP with yours:

```dart
class ApiConfig {
  static const String liveAuditWsHost = '192.168.1.158'; // ← your Mac's IP
  static const int liveAuditPort = 8000;
  static const String newsBaseUrl = 'http://192.168.1.158:8001'; // ← same IP
}
```

---

## Step 3 — Start the Live Audit Backend (port 8000)

This powers the Live Audit tab (real-time STT fact-checking).

```bash
cd dfacto_backend

# First time only: create venv and install deps
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Create .env with your API key
echo "GEMINI_API_KEY=your_key_here" > .env

# Start the server
source .venv/bin/activate
LANGCHAIN_TRACING_V2=false uvicorn main:app --host 0.0.0.0 --port 8000
```

You should see: `Uvicorn running on http://0.0.0.0:8000`

> **Tip:** The `start.sh` script does the activate + start in one step after first-time setup:
> ```bash
> bash dfacto_backend/start.sh
> ```

---

## Step 4 — Start the News Backend (port 8001)

This powers the News tab (keyword crawling + headline fact-checking).

```bash
cd "backend for news module"

# First time only: create venv and install deps
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install ddgs   # newer package name (replaces duckduckgo-search)

# Create .env (or verify it already has your key)
echo "GEMINI_API_KEY=your_key_here" > .env

# Start the server
source .venv/bin/activate
python main.py
```

You should see: `Uvicorn running on http://0.0.0.0:8001`

---

## Step 5 — Build and Run the Flutter App

Open a **third terminal tab** for this.

```bash
cd dfacto_app

# First time only
flutter pub get

# Connect your phone via USB, then:
flutter run

# Or build an APK and install it:
flutter build apk --debug
adb install build/app/outputs/flutter-apk/app-debug.apk
```

> For a release build (faster, smaller):
> ```bash
> flutter build apk --release
> adb install build/app/outputs/flutter-apk/app-release.apk
> ```

---

## Testing Each Feature

### Live Audit tab
1. Make sure the Live Audit backend (port 8000) is running
2. Open the app → tap **Live Audit**
3. Tap the **Start Listening** button
4. Speak a factual claim (e.g., *"The Eiffel Tower is in Paris"*)
5. Watch the transcript appear live, then a fact-check card pop up with a verdict and sources

### News tab
1. Make sure the News backend (port 8001) is running
2. Open the app → tap **News** (rightmost tab)
3. Tap the **tune icon** (top right) → enter keywords (e.g., `AI, climate change`) → set an interval → Save
4. Tap the **play icon** to trigger an immediate crawl
5. Wait ~30–60 seconds, then pull down to refresh — headlines with verdicts (TRUE / FALSE / MIXED) will appear
6. Tap any headline to see the full detail sheet with explanation and source link

---

## Quick-Start Cheat Sheet

```bash
# Terminal 1 — Live Audit backend
cd dfacto_backend
source .venv/bin/activate
LANGCHAIN_TRACING_V2=false uvicorn main:app --host 0.0.0.0 --port 8000

# Terminal 2 — News backend
cd "backend for news module"
source .venv/bin/activate
python main.py

# Terminal 3 — Flutter app (phone must be connected via USB)
cd dfacto_app
flutter run
```

> Note: both backends log to the terminal — keep them running while testing.
> The news crawler takes ~2–3 minutes after triggering to fully process 10+ headlines (Gemini fact-checks each one). This is normal.

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| "Cannot reach news backend" in app | News backend not running, or wrong IP in `api_config.dart` |
| Live Audit shows no fact-check cards | Live Audit backend not running, or WebSocket can't connect |
| `flutter run` hangs | Phone not in USB debug mode, or ADB not authorized — check phone screen for prompt |
| STT says "on-device GenAI not available" | Device doesn't support Android GenAI STT; try a Pixel 6+ or Galaxy S23+ |
| Gemini quota errors in backend logs | You've hit the free-tier RPM limit; wait a minute or upgrade your key |
| `pip install` fails for `duckduckgo-search` | Run `pip install --upgrade duckduckgo-search` |

---

## Environment Variables

### `dfacto_backend/.env`
```
GEMINI_API_KEY=your_key_here
```

### `backend for news module/.env`
```
GEMINI_API_KEY=your_key_here
```

Both backends use **Gemini** (free tier works). DuckDuckGo search (used by the News backend) requires no API key.

---

## Project Structure

```
dfacto/
├── dfacto_app/                    Flutter app
│   └── lib/
│       ├── core/
│       │   ├── config/api_config.dart     ← IP addresses live here
│       │   ├── theme/app_theme.dart
│       │   └── widgets/glass_container.dart
│       ├── features/
│       │   ├── live_audit/               Live Audit tab
│       │   ├── news/                     News tab
│       │   └── interactive/              Interactive tab (stub)
│       └── navigation/app_shell.dart     Tab bar + routing
│
├── dfacto_backend/                Live Audit backend (port 8000)
│   ├── main.py
│   ├── routers/live_audit.py      WebSocket endpoint
│   ├── agents/                    LangGraph fact-check pipeline
│   └── start.sh                   Quick-start script
│
└── backend for news module/       News Crawler backend (port 8001)
    ├── main.py
    ├── scheduler.py               APScheduler periodic crawl
    ├── database.py                SQLite storage
    └── agents/
        ├── workflow.py            DDG news search → Gemini extract
        ├── fact_checker.py        LangGraph fact-check pipeline
        └── tools.py               DuckDuckGo search helpers
```
