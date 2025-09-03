from __future__ import annotations

import json
import os
import sys
from typing import Any, Dict

# Import the tool function (decorated with @tool if smolagents is available)
#from src.lyrics_tool import search_song_by_lyrics

import re
import time
from dataclasses import dataclass
from typing import List, Optional, Tuple

import requests
from bs4 import BeautifulSoup
from ddgs import DDGS
from rapidfuzz import fuzz, process


USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
HEADERS = {"User-Agent": USER_AGENT, "Accept-Language": "en-US,en;q=0.9"}


def normalize_text(text: str) -> str:
    # Lowercase, strip, collapse whitespace, remove punctuation-like chars
    t = text.lower()
    t = re.sub(r"[\u2018\u2019\u201C\u201D]", "'", t)
    t = re.sub(r"[^a-z0-9\s\-\'&]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def fetch_url(url: str, timeout: int = 15) -> Optional[str]:
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout)
        if r.ok:
            return r.text
    except Exception:
        return None
    return None


LYRICS_HOST_PATTERNS = [
    # Common lyrics sites (no scraping of TOS-restricted behind auth/paywalls)
    r"genius\.com",
    r"azlyrics\.com",
    r"lyrics\.com",
    r"lyricfind\.com",
    r"songmeanings\.com",
    r"songfacts\.com",
    r"musixmatch\.com",
]


def extract_lyrics_from_html(html: str) -> Optional[str]:
    soup = BeautifulSoup(html, "lxml")

    # Heuristics: find large blocks of text inside article-like or lyric containers
    candidates = []

    # Genius
    for div in soup.select("[data-lyrics-container='true']"):
        txt = div.get_text("\n", strip=True)
        if txt:
            candidates.append(txt)

    # Generic article/p containers
    if not candidates:
        article = soup.find("article")
        if article:
            text = article.get_text("\n", strip=True)
            if text and len(text.split()) > 20:
                candidates.append(text)

    if not candidates:
        # look for likely lyric containers
        for sel in [
            ".lyrics",
            ".lyric",
            "#lyrics",
            "[class*='lyric']",
            "[id*='lyric']",
            "main",
        ]:
            for node in soup.select(sel):
                txt = node.get_text("\n", strip=True)
                if txt and len(txt.split()) > 20:
                    candidates.append(txt)

    if not candidates:
        # fallback: big block of paragraphs
        ps = soup.select("p")
        text = "\n".join(p.get_text(strip=True) for p in ps)
        if len(text.split()) > 20:
            candidates.append(text)

    if not candidates:
        return None

    # Choose the longest candidate
    best = max(candidates, key=lambda s: len(s))
    # Remove boilerplate
    best = re.sub(r"\b(chorus|verse|bridge|intro|outro):\s*", "", best, flags=re.I)
    # Collapse whitespace
    best = re.sub(r"\n{3,}", "\n\n", best)
    return best.strip()


@dataclass
class SongCandidate:
    title: str
    artist: Optional[str]
    url: str
    lyrics_snippet: Optional[str]
    score: float


def search_lyrics_pages(query: str, max_results: int = 10) -> List[Tuple[str, str]]:
    # Returns list of (title, url)
    results: List[Tuple[str, str]] = []
    with DDGS() as ddgs:
        for r in ddgs.text(query, region="wt-wt", safesearch="moderate", max_results=max_results*2):
            url = r.get("href") or r.get("url") or ""
            title = r.get("title") or ""
            if not url:
                continue
            if any(re.search(p, url) for p in LYRICS_HOST_PATTERNS):
                results.append((title, url))
            if len(results) >= max_results:
                break
    return results


def score_match(snippet: str, lyrics: str) -> float:
    # Use token sort ratio and partial ratio blend
    s_norm = normalize_text(snippet)
    l_norm = normalize_text(lyrics)
    r1 = fuzz.token_set_ratio(s_norm, l_norm)
    r2 = fuzz.partial_ratio(s_norm, l_norm)
    return 0.6 * r1 + 0.4 * r2


def infer_title_artist(title_text: str) -> Tuple[str, Optional[str]]:
    t = title_text
    # Patterns like "Artist - Song Lyrics | Genius" or "Song - Artist Lyrics"
    t = re.sub(r"\s*\|.*$", "", t)
    t = re.sub(r"\s*\(.*lyrics.*\)$", "", t, flags=re.I)
    t = re.sub(r"\s*lyrics\s*$", "", t, flags=re.I)

    parts = [p.strip() for p in re.split(r"\s+-\s+|:\s+", t) if p.strip()]
    if len(parts) >= 2:
        # Heuristic: either Artist - Song or Song - Artist
        left, right = parts[0], parts[1]
        if re.search(r"\b(feat\.|ft\.|with)\b", right, re.I):
            # likely song on left, features on right -> need artist separately
            return left, None
        # Prefer the part without 'lyrics' keyword as song
        if not re.search(r"lyrics", left, re.I):
            return parts[1], parts[0]  # Song, Artist
        else:
            return parts[0], parts[1]
    return t.strip(), None


def find_song_from_snippet(snippet: str, max_pages: int = 10, sleep_sec: float = 0.8) -> List[SongCandidate]:
    # Build search query
    quoted = '"' + snippet.strip().replace('"', '') + '" lyrics'
    pages = search_lyrics_pages(quoted, max_results=max_pages)
    candidates: List[SongCandidate] = []

    for title, url in pages:
        html = fetch_url(url)
        if not html:
            continue
        lyrics = extract_lyrics_from_html(html)
        if not lyrics:
            continue
        score = score_match(snippet, lyrics)
        song_title, artist = infer_title_artist(title)
        # Try to extract a small matching fragment to display
        frag = None
        try:
            # Use RapidFuzz extract to find best line
            lines = [ln.strip() for ln in lyrics.splitlines() if ln.strip()]
            match, mscore, _ = process.extractOne(snippet, lines, scorer=fuzz.partial_ratio)
            if match and mscore > 50:
                frag = match
        except Exception:
            frag = None

        candidates.append(SongCandidate(
            title=song_title,
            artist=artist,
            url=url,
            lyrics_snippet=frag,
            score=score,
        ))
        time.sleep(sleep_sec)

    # Sort by score desc
    candidates.sort(key=lambda c: c.score, reverse=True)
    return candidates


# smolagents Tool
from smolagents import tool


if tool:
    @tool
    def search_song_by_lyrics(snippet: str, max_pages: int = 8) -> dict:
        """Find the most likely song given a partial lyrics snippet.

        Args:
            snippet: A short piece of lyrics text.
            max_pages: How many lyrics pages to scan.

        Returns:
            A JSON object with a 'best' match and a 'alternatives' list.
        """
        results = find_song_from_snippet(snippet, max_pages=max_pages)
        if not results:
            return {"best": None, "alternatives": []}
        best = results[0]
        alts = [
            {"title": c.title, "artist": c.artist, "url": c.url, "score": round(c.score, 2), "match": c.lyrics_snippet}
            for c in results[1:5]
        ]
        return {
            "best": {
                "title": best.title,
                "artist": best.artist,
                "url": best.url,
                "score": round(best.score, 2),
                "match": best.lyrics_snippet,
            },
            "alternatives": alts,
        }


def _build_agent():
    """Create a smolagents ToolCallingAgent if credentials are available.
    """
    try:
        from smolagents import ToolCallingAgent
        from smolagents.models import LiteLLMModel
        model = LiteLLMModel(model_id="ollama_chat/qwen2.5-coder:32b-instruct-fp16",  api_base="https://ollama-ui.pagoda.liris.cnrs.fr/ollama", # replace with 127.0.0.1:11434 or remote open-ai compatible server if necessary 
                             api_key="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZCI6IjNlOTFhZDY3LWI3NGUtNGUzMC05YjU1LTk4YTM2MmEwNDFkOCIsImV4cCI6MTc4NDk2MjQzMX0.3w4rKHqkzTs6SeRZfcp6ghcvoiZUUfcYmI_iyklc61Y",)
                             
        agent = ToolCallingAgent(tools=[search_song_by_lyrics], model=model, max_steps=3)
        return agent, "qwen"
    except Exception:
        return None, None


def run(snippet: str) -> Dict[str, Any]:
    agent, backend = _build_agent()
    if agent is None:
        # Fallback: call the tool directly without an LLM
        result = search_song_by_lyrics(snippet)
        return {"backend": "direct", "result": result}

    instruction = (
        "Given a short lyrics snippet, call the tool `search_song_by_lyrics` to find the most likely song. "
        "Return a short JSON with the best match and 2-3 alternatives." \
        "Maybe the lyrics can be wrong, find the most similar ones."
    )
    query = f"Lyrics snippet: {snippet}"
    response = agent.run(instruction + "\n" + query)
    # When using ToolCallingAgent, it should return the tool's output as text; try to parse JSON if present.
    try:
        parsed = json.loads(response) if isinstance(response, str) else response
    except Exception:
        parsed = {"raw": response}
    return {"backend": backend, "result": parsed}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m src.run_agent \"we were only getting older...\"")
        sys.exit(1)
    snippet = " ".join(sys.argv[1:]).strip()
    out = run(snippet)
    print(json.dumps(out, indent=2, ensure_ascii=False))
