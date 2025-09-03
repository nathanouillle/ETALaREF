from __future__ import annotations

import argparse
import json
import os
import sys
from typing import List, Tuple

# Local imports
from whisper_song import transcribe_folder
from run_agent import run as run_search_agent


def read_transcripts_from_dir(out_dir: str) -> List[Tuple[str, str]]:
    items: List[Tuple[str, str]] = []
    if not os.path.isdir(out_dir):
        return items
    for name in sorted(os.listdir(out_dir)):
        if name.lower().endswith('.txt'):
            path = os.path.join(out_dir, name)
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    if content:
                        items.append((name, content))
            except Exception:
                # skip unreadable file
                pass
    return items


def main():
    parser = argparse.ArgumentParser(description="Transcribe audio files with Whisper then search lyrics online.")
    parser.add_argument("--folder", required=True, help="Folder containing .mp3 files")
    parser.add_argument("--model", default="base", help="Whisper model size (tiny, base, small, medium, large)")
    parser.add_argument("--language", default=None, help="Force language, e.g. 'en'")
    parser.add_argument("--out_dir", default="./transcriptions", help="Transcriptions output directory")
    parser.add_argument("--max_pages", type=int, default=8, help="Max lyrics pages to scan per search")
    args = parser.parse_args()

    # 1) Transcribe all MP3s in the folder
    transcribe_folder(args.folder, model_size=args.model, language=args.language, out_dir=args.out_dir)

    # 2) Collect transcripts and query the agent
    transcripts = read_transcripts_from_dir(args.out_dir)
    if not transcripts:
        print("No transcripts found to search.")
        sys.exit(0)

    all_results = []
    for i, (fname, full_text) in enumerate(transcripts, start=1):
        snippet = full_text[:350]  # keep search snippet short and distinctive
        print(f"\nSearching for {fname} (first 120 chars): {snippet[:120]}...")
        result = run_search_agent(snippet)
        all_results.append({
            "file": fname,
            "query_snippet": snippet,
            "result": result,
        })
        # Print a short summary to console
        try:
            payload = result.get("result", {}) if isinstance(result, dict) else {}
            best = payload.get("best") if isinstance(payload, dict) else None
            if best:
                title = best.get("title")
                artist = best.get("artist")
                url = best.get("url")
                score = best.get("score")
                print(f"  → Best match: {title} — {artist} | score={score} | {url}")
            else:
                print("  ! No best match returned")
        except Exception:
            print("  ! Unable to summarize result")

    # 3) Save aggregated results
    out_json = os.path.join(args.out_dir, "search_results.json")
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    print(f"\nSaved all search results to {out_json}")


if __name__ == "__main__":
    main()
