# Dfacto Frontend

The Dfacto frontend is a cross-platform web application built using **Flutter**. It provides a clean, user-friendly interface to configure the Dfacto backend crawler, view extracted news headlines, and review the rigorous fact-checking verdicts derived by the AI agents.

## Project Structure

- **`lib/main.dart`**: The application's entry point. It sets up the Material 3 theme (Dark mode by default) and initializes the `MainNavigationShell`, mapping out the bottom navigation tabs (Crawler, Audit, Verify, Settings).
- **`lib/screens/home_screen.dart`**: The core screen of the application. It fetches data from the backend to display the configuration form (Keywords & Interval) and a live-updating list of headlines. 
  - Headlines are categorized under their parsed target phrase.
  - Verdicts (TRUE, FALSE, MIXED) are presented cleanly using color-coded chips.
  - Users can tap a headline to open a detailed dialog showing the specific reasoning and explanation provided by the fact-checker agent.
- **`lib/services/api_service.dart`**: Handles all asynchronous HTTP requests to the FastAPI backend (`http://127.0.0.1:8000`). Manages fetching the `/config` and `/headlines`, as well as parsing them for the UI.

## Features

- **Configuration Control**: Update the keywords (comma separated) that the Agentic crawler should track, and modify the polling interval.
- **Manual Triggering**: Ability to test the background crawler instantly without waiting for the scheduler, utilizing the backend's background tasks.
- **Verdict Visualization**: Text clipping and ellipsis are properly handled to prevent UI truncation. Verdicts are categorical (the raw numerical confidence scores are intentionally abstracted from the UI for simplicity and clarity).
- **Explanations on Demand**: Detailed synthesis of exactly why a claim is rated as true, false, or mixed is safely housed under an interactive popup dialog.

## Setup and Running

Ensure you have the Flutter SDK installed on your system.

1. Navigate to the frontend directory: `cd frontend`
2. Fetch dependencies: `flutter pub get`
3. Run the web application for development: `flutter run -d chrome` 
   *(Alternatively run `flutter build web` and serve the build folder locally via python http.server)*

Note: Make sure your `backend` FastAPI server is running simultaneously on `localhost:8000` for the frontend to fetch data correctly.
