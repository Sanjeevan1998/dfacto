# Dfacto Frontend

This is the frontend application for Dfacto, built using Flutter. It provides a cross-platform mobile and web interface to view fact-checking results and control the agentic crawler backend.

## Features & Navigation

The application uses a bottom navigation bar with the following sections:

1. **Crawler (`HomeScreen`)**: The main dashboard that displays real-time headlines and data extracted by the backend crawler. It integrates with the FastAPI backend to fetch limits and trigger crawls manually.
2. **Audit (Phase 1)**: *(Work in Progress)* Designed for live audio auditing.
3. **Verify (Phase 2)**: *(Work in Progress)* Interface to verify specific claims.
4. **Settings**: Configuration settings for the app and crawler backend.

## Architecture

- **UI Framework**: Flutter (Material 3 Design).
- **Networking**: Uses the `http` package to communicate with the FastAPI backend.
- **State Management**: Uses standard Flutter state management for navigation and data fetching. 
- **Theme**: Dark mode by default with deep purple seed colors.

## Getting Started

To run the application, ensure you have the Flutter SDK installed and a device or emulator running.

```bash
# Fetch dependencies
flutter pub get

# Run the app
flutter run
```
