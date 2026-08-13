#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tts.py — יצירת קול (ראפ כדיבור קצבי) עם Kokoro TTS, מקומית ועל CPU בלבד.
Kokoro = 82M פרמטרים, Apache 2.0, בלי מפתח API ובלי מכסה.

השירה באנגלית (אילוץ הפרויקט). הכתוביות בעברית נוצרות בנפרד ב-tools/heb_ass.py.

שימוש:
  python3 tools/tts.py --text "Ten percent left..." --out assets/audio/vox.wav
  python3 tools/tts.py --text "..." --voice am_adam --speed 1.05 --out out.wav
"""
import argparse, sys, warnings
warnings.filterwarnings("ignore")
import numpy as np, soundfile as sf

SR = 24000   # Kokoro פולט 24kHz

def synth(text, voice="am_michael", speed=1.0, lang="a"):
    from kokoro import KPipeline
    pipe = KPipeline(lang_code=lang, repo_id="hexgrad/Kokoro-82M")
    chunks = []
    for _, _, audio in pipe(text, voice=voice, speed=speed):
        chunks.append(np.asarray(audio, dtype=np.float32))
    if not chunks:
        raise RuntimeError("Kokoro לא החזיר אודיו")
    return np.concatenate(chunks)

def main():
    p = argparse.ArgumentParser(description="Kokoro TTS מקומי")
    p.add_argument("--text", required=True); p.add_argument("--out", required=True)
    p.add_argument("--voice", default="am_michael")   # קול גברי אמריקאי
    p.add_argument("--speed", type=float, default=1.0)
    p.add_argument("--lang", default="a")             # a = American English
    p.add_argument("--seconds", type=float, default=None, help="חתוך/רפד לאורך מדויק")
    a = p.parse_args()
    y = synth(a.text, a.voice, a.speed, a.lang)
    if a.seconds:
        n = int(a.seconds * SR)
        y = y[:n] if len(y) >= n else np.pad(y, (0, n - len(y)))
    peak = float(np.max(np.abs(y))) or 1.0
    y = (y / peak) * 0.92
    sf.write(a.out, y, SR, subtype="PCM_16")
    print(f"נכתב: {a.out}  {len(y)/SR:.2f}s @ {SR}Hz  קול={a.voice}")

if __name__ == "__main__":
    sys.exit(main())
