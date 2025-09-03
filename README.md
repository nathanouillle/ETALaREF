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
- `src/lyrics_tool.py` — Search/scrape/match logic and a `@tool` exposed to smolagents.
- `src/run_agent.py` — Minimal runner that either calls the tool directly or via a smolagents ToolCallingAgent if you provide API keys.
- `requirements.txt` — Python dependencies.
- `.env.example` — Optional environment variables for LLM backends.

Setup
-----
1) Create and activate a virtual environment (Windows PowerShell):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

2) (Optional) Copy `.env.example` to `.env` and fill in keys if you want an LLM to orchestrate the tool; otherwise it will run the tool directly.

Usage
-----
Run the agent with a snippet:

```powershell
python -m src.run_agent "and I think to myself what a wonderful world"
```

You’ll get a JSON payload with the backend used (`direct` if no LLM) and the `result` containing the best match and alternatives.

Notes
-----
- Be respectful of website terms of service. This uses light scraping heuristics and throttles requests.
- Matching is fuzzy; provide at least ~6–8 words for better accuracy.
- For LLM-backed flows, set `OPENAI_API_KEY` (and optionally `OPENAI_MODEL`) or configure a LiteLLM `LITELLM_MODEL` with `HF_API_KEY`.
# ETALaREF
Chante moi la musique et je te la trouve
