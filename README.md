ETALaREF — Lyrics-to-Song Agent
================================

This repo contains a small Hugging Face smolagents-based tool and agent that, given a short lyrics snippet, searches the web for lyrics pages and returns the most likely song.

What it does
------------
- Uses DuckDuckGo search to find likely lyrics pages (Genius, AZLyrics, etc.).
- Scrapes the page and extracts the lyrics with simple heuristics.
- Compares your snippet to the extracted lyrics with fuzzy matching.
- Returns the best match and a few alternatives.

Project layout
--------------
- `src/run_agent.py` — Minimal runner that either calls the tool via smolagents.
- `requirements.txt` — Python dependencies.

Usage
-----
Run the agent with a snippet:

```bash
./src.run_agent "and I think to myself what a wonderful world"
```

You’ll get a JSON payload with the backend used (`direct` if no LLM) and the `result` containing the best match and alternatives.
