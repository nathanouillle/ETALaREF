ETALaREF — Lyrics-to-Song Agent
================================

Find a song from a short lyrics snippet. You can:
- Transcribe audio files to text using Whisper.
- Search the web (Genius, AZLyrics, etc.) and fuzzy-match your snippet to lyrics.
- Run both steps end-to-end with one command.

What it does
------------
- Uses DuckDuckGo search to find likely lyrics pages (Genius, AZLyrics, Lyrics.com, Musixmatch).
- Scrapes pages and extracts lyrics with simple heuristics.
- Fuzzy-matches your snippet against extracted lyrics and ranks results.
- Works with or without an LLM backend (falls back to a direct tool call).

Project layout
--------------
- `src/run_agent.py` — Search a lyrics snippet on the web and return best match + alternatives.
- `src/whisper_song.py` — Transcribe all `.mp3` files in a folder to `transcriptions/*.txt`.
- `src/orchestrate_transcribe_and_search.py` — End-to-end: transcribe then search each transcript; saves `transcriptions/search_results.json`.
- `data/` — Put your `.mp3` here (example: `diamonds.mp3`).
- `transcriptions/` — Transcribed text and aggregated search results.
- `requirements.txt` — Python dependencies.

Requirements
------------
- Python 3.11+ recommended
- ffmpeg installed and available in PATH (required by Whisper)
	- Windows (optional): `choco install ffmpeg` or install from ffmpeg.org

Setup
-----
PowerShell (Windows):

```powershell
python -m venv .venv; .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Usage
-----
1) Search directly from a lyrics snippet

```powershell
python -m src.run_agent "and I think to myself what a wonderful world"
```

2) Transcribe `.mp3` files to text only

```powershell
python -m src.whisper_song --folder data --model base --language en --out_dir transcriptions
```

3) End-to-end: transcribe, then search each transcript

```powershell
python -m src.orchestrate_transcribe_and_search --folder data --model base --language en --out_dir transcriptions --max_pages 8
```

Outputs
-------
- Transcriptions: `transcriptions/<audio_basename>.txt`
- Aggregated search results: `transcriptions/search_results.json`
	- Includes, per file: the query snippet used, backend info, and the tool’s best match (title, artist, url, score) plus alternatives.

Notes & tips
------------
- Only `.mp3` files are transcribed by default. Convert other formats to `.mp3` or adapt `src/whisper_song.py`.
- If Whisper is slow, try smaller models (`tiny`, `base`, `small`). Use `--language en` to speed up English.
- The search agent runs without an LLM if no compatible endpoint is reachable (backend will show `direct`).
- If you see import errors, ensure you activated the virtual environment and ran `pip install -r requirements.txt`.
