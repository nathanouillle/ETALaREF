
import os
import argparse
from typing import Optional

def transcribe_folder(folder: str, model_size: str = "base", language: Optional[str] = None, out_dir: str = './transcriptions'):
    # Lazy import so modules that depend on this file don't require whisper at import time
    import whisper
    model = whisper.load_model(model_size)
    os.makedirs(out_dir, exist_ok=True)

    files = [f for f in os.listdir(folder) if f.lower().endswith(".mp3")]
    if not files:
        print("No .mp3 files found in", folder)
        return

    for f in files:
        path = os.path.join(folder, f)
        print(f"\nTranscribing: {f}")
        try:
            result = model.transcribe(path, language=language)
            text = result["text"].strip()

            out_path = os.path.join(out_dir,f.split('.')[0] + ".txt")
            with open(out_path, "w", encoding="utf-8") as out:
                out.write(text)

            print(f"  → Saved transcript to {out_path}")
        except Exception as e:
            print(f"  ! Error transcribing {f}: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--folder", required=True, help="Path to folder with .mp3 files")
    parser.add_argument("--model", default="base", help="Whisper model size (tiny, base, small, medium, large)")
    parser.add_argument("--language", default=None, help="Force language (e.g., 'en' for English)")
    parser.add_argument("--out_dir", default="./transcriptions", help="Directory to save transcriptions")
    args = parser.parse_args()

    transcribe_folder(args.folder, args.model, args.language, args.out_dir)
