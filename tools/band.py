#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
band.py — ליווי בכלים מוקלטים אמיתיים, מסגנונות מוכנים. בלי לסנתז כלום.

🔴 למה הכלי הזה קיים: הסינתזה הפרוצדורלית ב-`chords.py` נשמעת "חיוורת"
בכלים אקוסטיים — פסנתר, גיטרה, כלי קשת. הסיבה פשוטה: כלי אמיתי הוא הקלטה,
לא נוסחה. במקום לנסות לחקות אותו, הכלי הזה **משתמש בהקלטות מוכנות**:

  • **MMA** (Musical MIDI Accompaniment) — 119 סגנונות ליווי מוכנים, בדיוק
    כמו ה"סטיילים" של אורגנית. נותן תבנית נגינה מקצועית לכל ז׳אנר.
  • **FluidR3 GM** — סאונדפונט של כלים מוקלטים. **רישיון MIT** (חינם גם
    לשימוש מסחרי), 142MB, מותקן דרך apt. אפס עלות, אפס רשת, אפס GPU.
  • **FluidSynth** — מנגן את ה-MIDI דרך הסאונדפונט.

מתי להשתמש במה:
  `band.py`   — פסנתר, גיטרה, כלי קשת, נשיפה, תופים אקוסטיים, ליווי שלם
  `chords.py` — פדים סינתטיים, סטאבים, סאב-באס, כל מה שאמור להישמע אלקטרוני
  `beat.py`   — תופים אלקטרוניים ו-808. **ה-GM לא מכיל 808 מודרני**

שימוש:
  python3 tools/band.py --list
  python3 tools/band.py --out band.wav --style PopBallad --bpm 104 --key Am --prog "i VI III VII"
  python3 tools/band.py --out band.wav --style BossaNova --bpm 96 --key C --prog "I vi ii V" --repeat 4
"""
import argparse, os, shutil, subprocess, sys, tempfile
import numpy as np, soundfile as sf

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import chords as CH

SR = 44100
SF2_CANDIDATES = [
    "/usr/share/sounds/sf2/FluidR3_GM.sf2",
    "/usr/share/sounds/sf2/default-GM.sf2",
    "/usr/share/soundfonts/FluidR3_GM.sf2",
]
STYLE_DIR = "/usr/share/mma/lib/stdlib"
NAMES = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]


def find_sf2():
    for p in SF2_CANDIDATES:
        if os.path.exists(p):
            return p
    raise SystemExit("⛔ לא נמצא סאונדפונט. להתקין:\n"
                     "   apt-get install -y fluidsynth fluid-soundfont-gm mma")


def list_styles():
    """שמות הגרוב'ים בפועל — שם הקובץ אינו שם הגרוב."""
    if not os.path.isdir(STYLE_DIR):
        raise SystemExit(f"⛔ MMA לא מותקן ({STYLE_DIR} חסר). apt-get install -y mma")
    out = []
    for fn in sorted(os.listdir(STYLE_DIR)):
        if not fn.endswith(".mma"):
            continue
        with open(os.path.join(STYLE_DIR, fn), errors="ignore") as f:
            for line in f:
                if line.startswith("DefGroove"):
                    out.append(line.split()[1])
    return out


def chord_name(numeral, root_pc, scale):
    """דרגה רומית -> שם אקורד ש-MMA מבין (Am, F, G7 ...)."""
    ns = CH.chord_midi(numeral, root_pc, scale, octave=3)
    root = ns[0] % 12
    iv = sorted({(x - ns[0]) % 12 for x in ns[1:]})
    if iv[:2] == [3, 7]:
        q = "m"
    elif iv[:2] == [3, 6]:
        q = "dim"
    elif iv[:2] == [4, 7]:
        q = ""
    else:
        q = ""
    if len(ns) > 3:                      # אקורד שביעי
        q += "7" if q in ("", "m") else ""
    return NAMES[root] + q


def build(style, bpm, key, prog, repeat, sf2, gain=0.9, seed=None):
    for exe in ("mma", "fluidsynth"):
        if not shutil.which(exe):
            raise SystemExit(f"⛔ '{exe}' לא מותקן. apt-get install -y fluidsynth fluid-soundfont-gm mma")
    root_pc, scale = CH.parse_key(key)
    numerals = prog.replace(",", " ").split()
    tmp = tempfile.mkdtemp(prefix="band_")
    src = os.path.join(tmp, "song.mma")
    with open(src, "w") as f:
        f.write(f"Tempo {bpm}\nGroove {style}\n")
        bar = 1
        for _ in range(repeat):
            for num in numerals:
                f.write(f"{bar} {chord_name(num, root_pc, scale)}\n")
                bar += 1
    r = subprocess.run(["mma", src], capture_output=True, text=True)
    mid = os.path.join(tmp, "song.mid")
    if r.returncode != 0 or not os.path.exists(mid):
        err = (r.stderr or r.stdout).strip()
        if "could not be found" in err:
            err += "\n   הרשימה המלאה: python3 tools/band.py --list"
        raise SystemExit(f"⛔ MMA נכשל:\n{err}")
    wav = os.path.join(tmp, "song.wav")
    r = subprocess.run(["fluidsynth", "-ni", "-F", wav, "-r", str(SR), "-g", str(gain),
                        sf2, mid], capture_output=True, text=True)
    if r.returncode != 0 or not os.path.exists(wav):
        raise SystemExit(f"⛔ fluidsynth נכשל:\n{(r.stderr or r.stdout).strip()}")
    y, sr = sf.read(wav, always_2d=True)
    shutil.rmtree(tmp, ignore_errors=True)
    if y.shape[1] == 1:
        y = np.repeat(y, 2, axis=1)
    return y.astype(np.float32), sr


def main():
    p = argparse.ArgumentParser(description="ליווי בכלים אמיתיים מסגנונות מוכנים")
    p.add_argument("--out")
    p.add_argument("--style", default="PopBallad")
    p.add_argument("--bpm", type=float, default=104)
    p.add_argument("--key", default="Am")
    p.add_argument("--prog", default="i VI III VII")
    p.add_argument("--repeat", type=int, default=2, help="כמה פעמים לחזור על הרצף")
    p.add_argument("--gain", type=float, default=0.9)
    p.add_argument("--sf2", default=None)
    p.add_argument("--list", action="store_true", help="רשימת הסגנונות המוכנים")
    a = p.parse_args()

    if a.list:
        st = list_styles()
        print(f"{len(st)} סגנונות מוכנים:\n")
        for i in range(0, len(st), 4):
            print("   " + "".join(f"{x:<24}" for x in st[i:i + 4]))
        return
    if not a.out:
        p.error("צריך --out (או --list)")

    y, sr = build(a.style, a.bpm, a.key, a.prog, a.repeat, a.sf2 or find_sf2(), a.gain)
    sf.write(a.out, y, sr, subtype="PCM_16")
    print(f"נכתב: {a.out}  {len(y)/sr:.1f}s @ {a.bpm} BPM, {a.key}, "
          f"סגנון={a.style}, רצף={a.prog}×{a.repeat}")


if __name__ == "__main__":
    main()
