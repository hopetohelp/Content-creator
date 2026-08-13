#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""assemble.py — שרשור הקטעים, מיזוג האודיו, וצריבת הכתוביות. הקובץ הסופי.

שלושה שלבים, בסדר הזה:
1. **concat** של כל הקטעים מ-`output/segments/` לפי סדר רשימת השוטים.
   הקטעים כבר חולקו כך שכל חיתוך נופל על גבול תיבה — החיתוכים על הדופק.
2. **צריבת הכתוביות** דרך libass, עם `fontsdir=./fonts`.
3. **מיזוג האודיו** מ-`assets/audio/mix.wav` וקידוד ל-AAC.

🔴 המילים המודגשות (10% · TOKENS · BATTERY) **כבר בתוך השוטים**, בשכבת
`gfx` של `shot_kit.py` — לא בשורת הכתובית. ערבוב לטיני-עברי באותה שורה
שובר bidi ו-`10%` מתהפך ל-`%10`. ראו CLAUDE.md פרק 5.

שימוש:
    python3 tools/assemble.py --out output/final.mp4
"""
import argparse, json, os, subprocess, sys

SEG_DIR = "output/segments"
SHOTLIST = "assets/shots/shotlist.json"
AUDIO = "assets/audio/mix.wav"
SUBS = "subs/clip.ass"
FPS = 30


def run(cmd, what):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"⛔ {what} נכשל:\n{r.stderr[-1200:]}")
    return r


def probe(path, entries, stream=None):
    cmd = ["ffprobe", "-v", "error"]
    if stream:
        cmd += ["-select_streams", stream]
    cmd += ["-show_entries", entries, "-of", "default=nw=1:nk=1", path]
    return subprocess.run(cmd, capture_output=True, text=True).stdout.split()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--out", default="output/final.mp4")
    p.add_argument("--no-subs", action="store_true", help="גרסה בלי כתוביות, לבדיקה")
    a = p.parse_args()

    shots = json.load(open(SHOTLIST, encoding="utf-8"))
    missing = [s["id"] for s in shots
               if not os.path.exists(os.path.join(SEG_DIR, f"{s['id']}.mp4"))]
    if missing:
        raise SystemExit(f"⛔ חסרים קטעים: {', '.join(missing)}")

    # 1. רשימת ה-concat, לפי סדר ציר הזמן
    lst = os.path.join(SEG_DIR, "concat.txt")
    with open(lst, "w", encoding="utf-8") as f:
        for s in shots:
            f.write(f"file '{os.path.abspath(os.path.join(SEG_DIR, s['id'] + '.mp4'))}'\n")

    silent = os.path.join(SEG_DIR, "_joined.mp4")
    run(["ffmpeg", "-v", "error", "-f", "concat", "-safe", "0", "-i", lst,
         "-c", "copy", silent, "-y"], "concat")

    vdur = float(probe(silent, "format=duration")[0])
    print(f"  שורשרו {len(shots)} קטעים → {vdur:.2f} שניות")

    # 2+3. כתוביות ואודיו במעבר אחד
    vf = [] if a.no_subs else [f"subtitles={SUBS}:fontsdir=./fonts"]
    cmd = ["ffmpeg", "-v", "error", "-i", silent, "-i", AUDIO]
    if vf:
        cmd += ["-vf", ",".join(vf)]
    cmd += ["-map", "0:v:0", "-map", "1:a:0",
            "-c:v", "libx264", "-preset", "medium", "-crf", "19",
            "-pix_fmt", "yuv420p", "-r", str(FPS),
            "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "2",
            "-shortest", "-movflags", "+faststart", a.out, "-y"]
    run(cmd, "צריבת כתוביות ומיזוג אודיו")

    # אימות — קוד יציאה 0 אינו הוכחה
    dur = float(probe(a.out, "format=duration")[0])
    vs = probe(a.out, "stream=codec_name,width,height,pix_fmt", "v:0")
    as_ = probe(a.out, "stream=codec_name,channels", "a:0")
    print(f"\nנכתב: {a.out}")
    print(f"   משך      : {dur:.2f} שניות")
    print(f"   וידאו    : {' '.join(vs)}")
    print(f"   אודיו    : {' '.join(as_)}")

    ok = True
    if not (85.0 <= dur <= 95.0):
        print(f"   ⛔ המשך {dur:.2f} מחוץ לטווח 85–95"); ok = False
    if not vs or vs[3] != "yuv420p":
        print("   ⛔ pix_fmt אינו yuv420p"); ok = False
    if not as_:
        print("   ⛔ אין ערוץ אודיו"); ok = False
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
