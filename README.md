# Dfacto

**Team Name:** Facters
**Team Members:** Erin Kong, Arnab Bhowal, Nasir Hasan Dilawar, and Sanjeevan Adhikari

Currently in development, Dfacto aims to provide comprehensive, real-time fact-checking across various modalities. The application is designed to support four core features:

1. **Live Conversation Fact-Checking**: Auditing live audio (e.g., debates, interviews) to fact-check statements in real-time with proper sources.
2. **Media & Link Verification**: Analyzing shared images, videos, and URLs to verify the authenticity of the contents.
3. **Interactive Mode**: A conversational interface where users can chat with the app to get help fact-checking specific claims.
4. **Agentic News Crawler**: Continuously monitoring the web for live, factual news based on user-preset keywords and schedules.

## Branches & Working Modules

Since this was a hackathon project, we didn't get the time to complete everything and integrate it together, so the working modules are in different branches. Here are the branch names and what each branch contains:

- **`main`** - Only has News Search based on keyword and fact check on the found news.
- **`feature/multimodalnewssearch`** - Only has News Search based on keyword and fact check on the found news. But the different element is that unlike `main`, it gets the news data and does the fact checking using a browser agent, which replicates how a user would do a fact check in real time.
- **`live-v2-working`** - Final working version of `live-audit` from `live-audit-v2` with minor bug fixes.
- **`live-audit-v3`** - Added the changes to make it decoupled.
- **`live-audit-v2`** - Perfected the live fact checking with real time audio stream with real time follow up questions for the fact check results.
- **`live-audit`** - Initial changes with just the live transcription of the real time audio stream.
- **`ux-ui`** - This stores the UI changes.
