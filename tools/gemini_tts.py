#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gemini_tts.py — קול דרך Gemini TTS. חינם רשמית, ולכן מותר במסלול A.

**למה בנוסף ל-`tts.py`:** `tts.py` מריץ Kokoro מקומית — 330MB הורדה בכל
סשן, ובלי שליטה על **סגנון המסירה**. ל-Gemini אפשר לומר "יבש ואדיש" מול
"בפאניקה" מול "בצעקה", וזה בדיוק מה שבונה את קשת המסירה של השיר
(בית 1 אדיש ← בית 2 פאניקה ← פזמון בצעקה ← סוף בלחישה).
`tts.py` נשאר הגיבוי כשאין רשת.

🔴 **קול גברי בלבד.** אילוץ קשיח של הפרויקט (CLAUDE.md פרק 1). כאן אין
מוסכמת-שם כמו ב-Kokoro, ולכן ההגנה היא **רשימת היתר סגורה** — כל שם שלא
ברשימה נדחה, גם אם הוא תקין אצל Google. זאת ועוד: רשימת היתר אינה הוכחה,
ולכן כל קובץ נבדק **במדידה על האודיו עצמו** לפני שהוא נכנס לריפו —
הנוהל בסעיף 8 של `מסמכים/6. הנחיות הפקה מומלצות.md`.

הכלי **ניתן להמשכה**: קובץ שכבר קיים ותקין מדולג. סשן שנקטע ממשיך מאיפה
שנעצר במקום להתחיל מחדש.

שימוש:
  python3 tools/gemini_tts.py --text "Ten percent battery." --out line.wav
  python3 tools/gemini_tts.py --json lines.json --outdir assets/audio/vox
"""
import argparse, base64, io, json, os, subprocess, sys, time
import urllib.error, urllib.request

MODEL = "gemini-3.1-flash-tts-preview"
API = "https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={k}"
PCM_RATE = 24000            # המודל מחזיר PCM גולמי 24kHz מונו, בלי כותרת
OUT_RATE = 44100            # קצב הדגימה של שאר שרשרת האודיו בריפו

# 🔴 רשימת היתר סגורה — קולות גבריים בלבד. ברירת המחדל היא סירוב.
MALE_VOICES = {"charon", "puck", "fenrir", "orus"}


def assert_male(voice: str) -> None:
    """חוסם כל קול שאינו ברשימת הגברים המפורשת. ראו CLAUDE.md פרק 1."""
    if (voice or "").strip().lower() in MALE_VOICES:
        return
    raise SystemExit(
        f"⛔ הקול '{voice}' נדחה.\n"
        "   איסור גורף בפרויקט: אין להשתמש בקול אישה בשום תוצר — כולל בדיקות,\n"
        "   דוגמאות, מדריכים ומחקרים. ראו CLAUDE.md פרק 1.\n"
        "   ב-Gemini אין מוסכמת-שם למגדר, ולכן מותרים רק: "
        + ", ".join(sorted(MALE_VOICES)) + ".\n"
        "   להוסיף קול לרשימה רק אחרי בדיקת מגדר במדידה על אודיו שנוצר ממנו."
    )


def synth(text: str, style: str, voice: str, key: str, retries: int = 4) -> bytes:
    """מחזיר PCM גולמי. מנסה שוב עם השהיה גדלה — ה-API מגביל קצב."""
    prompt = f"{style}: {text}" if style else text
    body = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice}}},
        },
    }).encode("utf-8")

    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(
                API.format(m=MODEL, k=key), data=body,
                headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=120) as r:
                data = json.loads(r.read().decode("utf-8"))
            for part in data["candidates"][0]["content"]["parts"]:
                if "inlineData" in part:
                    return base64.b64decode(part["inlineData"]["data"])
            last = f"אין אודיו בתשובה: {json.dumps(data)[:200]}"
        except (urllib.error.URLError, urllib.error.HTTPError, KeyError, IndexError) as e:
            last = repr(e)
        time.sleep(2 ** attempt)
    raise SystemExit(f"⛔ Gemini TTS נכשל אחרי {retries} ניסיונות: {last}")


def pcm_to_wav(pcm: bytes, out_path: str) -> None:
    """‎-f s16le -ar 24000 -ac 1 הם חובה — המודל מחזיר PCM בלי כותרת."""
    p = subprocess.run(
        ["ffmpeg", "-v", "error", "-f", "s16le", "-ar", str(PCM_RATE), "-ac", "1",
         "-i", "pipe:0", "-ar", str(OUT_RATE), "-ac", "1", out_path, "-y"],
        input=pcm, capture_output=True)
    if p.returncode != 0:
        raise SystemExit(f"⛔ ffmpeg נכשל: {p.stderr.decode()[:300]}")


def measure(path: str):
    """משך ועוצמה. פקודה שהחזירה 0 אינה הוכחה — CLAUDE.md פרק 6."""
    dur = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                          "format=duration", "-of", "csv=p=0", path],
                         capture_output=True, text=True).stdout.strip()
    vd = subprocess.run(["ffmpeg", "-hide_banner", "-i", path, "-af", "volumedetect",
                         "-f", "null", "/dev/null"], capture_output=True, text=True).stderr
    mean = next((l.split("mean_volume:")[1].strip() for l in vd.splitlines()
                 if "mean_volume:" in l), "?")
    return (float(dur) if dur else 0.0), mean


def is_valid(path: str) -> bool:
    if not os.path.exists(path) or os.path.getsize(path) < 2000:
        return False
    dur, mean = measure(path)
    try:
        return dur > 0.2 and float(mean.split()[0]) > -40.0
    except (ValueError, IndexError):
        return False


def main():
    p = argparse.ArgumentParser(description="קול דרך Gemini TTS — גברי בלבד")
    p.add_argument("--text"); p.add_argument("--out")
    p.add_argument("--json", help='[{"id":..,"text":..,"style":..}]')
    p.add_argument("--outdir")
    p.add_argument("--voice", default="Charon")
    p.add_argument("--style", default="", help="הנחיית מסירה, למשל: Say dry and deadpan")
    p.add_argument("--force", action="store_true", help="לייצר מחדש גם קובץ קיים ותקין")
    a = p.parse_args()

    assert_male(a.voice)
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        raise SystemExit("⛔ אין GEMINI_API_KEY בסביבה.")

    if a.text and a.out:
        items = [{"id": os.path.splitext(os.path.basename(a.out))[0],
                  "text": a.text, "style": a.style}]
        paths = {items[0]["id"]: a.out}
    elif a.json and a.outdir:
        items = json.load(io.open(a.json, encoding="utf-8"))
        os.makedirs(a.outdir, exist_ok=True)
        paths = {it["id"]: os.path.join(a.outdir, f"{it['id']}.wav") for it in items}
    else:
        raise SystemExit("⛔ צריך --text ו---out, או --json ו---outdir.")

    made = skipped = 0
    for it in items:
        out = paths[it["id"]]
        if not a.force and is_valid(out):
            skipped += 1
            continue
        pcm = synth(it["text"], it.get("style", a.style), a.voice, key)
        pcm_to_wav(pcm, out)
        dur, mean = measure(out)
        if dur <= 0.2 or float(mean.split()[0]) < -40.0:
            raise SystemExit(f"⛔ {out}: {dur:.2f}s, {mean} — שקט או ריק. כישלון.")
        print(f"  ✅ {it['id']:8s} {dur:5.2f}s  {mean:>10s}  {out}")
        made += 1
        time.sleep(0.6)          # ידידותי למגבלת הקצב

    print(f"נוצרו {made} קבצים, דולגו {skipped} שכבר היו תקינים. קול: {a.voice}")


if __name__ == "__main__":
    main()
