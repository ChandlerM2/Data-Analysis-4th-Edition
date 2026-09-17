"""Turn text into a short audio file: boss memos for tickets, or any rep read aloud.

    uv run --no-project --with edge-tts python PRACTICE/tools/speak.py OUT_STEM --text "..." [--voice NAME]

Tries edge-tts first (natural voices, needs internet; it uses Microsoft Edge's online voice
service without official support, so it can stop working). When edge-tts is missing or fails,
falls back to the voice built into the operating system: System.Speech on Windows, `say` on
macOS, `espeak-ng` on Linux. If `uv run --with edge-tts` itself fails offline, run the same
command without `--with edge-tts` to go straight to the fallback.

Prints the path of the file it wrote: OUT_STEM.mp3 from edge-tts, OUT_STEM.wav from the fallback.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import shutil
import subprocess
import sys
from pathlib import Path


def with_edge_tts(text: str, voice: str, stem: Path) -> Path:
    import edge_tts  # imported here so the OS fallback works without it

    out = stem.with_suffix(".mp3")
    asyncio.run(edge_tts.Communicate(text, voice).save(str(out)))
    return out


def with_os_voice(text: str, stem: Path) -> Path:
    out = stem.with_suffix(".wav")
    if sys.platform == "win32":
        # Pass the text through an environment variable so quotes in it can't break the command.
        script = ("Add-Type -AssemblyName System.Speech; "
                  "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
                  f"$s.SetOutputToWaveFile('{out}'); $s.Speak($env:SPEAK_TEXT); $s.Dispose()")
        subprocess.run(["powershell", "-NoProfile", "-Command", script], check=True,
                       env={**os.environ, "SPEAK_TEXT": text})
    elif sys.platform == "darwin":
        subprocess.run(["say", "--file-format=WAVE", "--data-format=LEI16", "-o", str(out), text], check=True)
    else:
        program = shutil.which("espeak-ng") or shutil.which("espeak")
        if program is None:
            raise SystemExit("No speech engine found. Install espeak-ng, or run with internet for edge-tts.")
        subprocess.run([program, "-w", str(out), text], check=True)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("stem", type=Path, help="output path without an extension")
    parser.add_argument("--text", required=True)
    parser.add_argument("--voice", default="en-US-AndrewNeural")
    args = parser.parse_args()
    args.stem.parent.mkdir(parents=True, exist_ok=True)
    try:
        out = with_edge_tts(args.text, args.voice, args.stem)
    except Exception as exc:  # any edge-tts failure: missing package, no network, service change
        print(f"edge-tts unavailable ({type(exc).__name__}); using the operating system voice.", file=sys.stderr)
        out = with_os_voice(args.text, args.stem)
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
