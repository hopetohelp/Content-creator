#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""voice_gender.py — שער חוסם: אין קול אישה בשום תוצר.

**למה זה קיים:** `tts.py` חוסם מזהי-קול נשיים ו-`gemini_tts.py` מחזיק רשימת
היתר — אבל שניהם חוסמים **את השם**, לא את הצליל. קול שמגיע מ-Lyria, מקובץ
שהורד, או ממודל שהתעלם מהבקשה, לא עובר דרך אף אחד מהם. הכלי הזה בודק את
**האודיו עצמו**. ראו CLAUDE.md פרק 1 ומסמך 6 סעיף 8.

🔑 **קובץ בקרה — החלק החשוב בכלי.** בכל הרצה נשלח גם קובץ שידוע שהוא גברי.
אם השופט טועה בבקרה, **הבדיקה פגומה — לא התוצר**, והכלי נופל במקום להכריז
על כשל שווא. בריפו הזה בדיקות מדידה כבר החזירו תוצאה שגויה ארבע פעמים כי
הבדיקה עצמה הייתה שבורה. ראו CLAUDE.md פרק 6.

🔴 **לא למדוד תדר יסוד (F0).** נוסה, ונכשל: על מיקס מלא הוא מודד סינתיסייזרים
והאטס ולא את הקול, והחזיר "אישה" על שירה גברית. רק מודל ששומע את האודיו נותן
תשובה אמינה.

שימוש:
  python3 tools/voice_gender.py assets/audio/vox/*.wav
  python3 tools/voice_gender.py --control tests/research/gemini_tts_line.wav mix.wav
"""
import argparse, base64, glob, json, os, sys, time
import urllib.error, urllib.request

MODEL = "gemini-3.1-flash-lite"        # חינם רשמית — ולכן הבדיקה תקפה גם במסלול A
API = "https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={k}"
DEFAULT_CONTROL = "tests/research/gemini_tts_line.wav"

MIME = {".wav": "audio/wav", ".mp3": "audio/mpeg", ".m4a": "audio/mp4",
        ".ogg": "audio/ogg", ".flac": "audio/flac"}

PROMPT = ('Listen to this audio. Is the speaking or singing voice male or female? '
          'If there is no voice at all, answer "none". Answer ONLY with JSON: '
          '{"voice_gender":"male"|"female"|"none"|"unclear",'
          '"confidence":"high"|"medium"|"low"}')


def judge(path, key, retries=4):
    ext = os.path.splitext(path)[1].lower()
    if ext not in MIME:
        raise SystemExit(f"⛔ סוג קובץ לא נתמך: {path}")
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("ascii")
    body = json.dumps({"contents": [{"parts": [
        {"inline_data": {"mime_type": MIME[ext], "data": b64}},
        {"text": PROMPT}]}]}).encode("utf-8")

    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(API.format(m=MODEL, k=key), data=body,
                                         headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=180) as r:
                data = json.loads(r.read().decode("utf-8"))
            txt = data["candidates"][0]["content"]["parts"][0]["text"]
            txt = txt.strip().removeprefix("```json").removeprefix("```").removesuffix("```")
            return json.loads(txt.strip())
        except Exception as e:                      # noqa: BLE001 — כל כשל שווה ניסיון נוסף
            last = repr(e)
            time.sleep(2 ** attempt)
    raise SystemExit(f"⛔ השופט נכשל על {path} אחרי {retries} ניסיונות: {last}")


def main():
    p = argparse.ArgumentParser(description="שער חוסם למגדר הקול")
    p.add_argument("files", nargs="+")
    p.add_argument("--control", default=DEFAULT_CONTROL,
                   help="קובץ שידוע שהוא גברי. אם השופט טועה בו — הבדיקה פגומה")
    p.add_argument("--allow-none", action="store_true",
                   help="לקבל קובץ בלי קול כלל (למשל אינסטרומנטל)")
    a = p.parse_args()

    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        raise SystemExit("⛔ אין GEMINI_API_KEY בסביבה.")

    # 1. הבקרה — לפני הכול. בדיקה שנכשלת בבקרה אינה ראויה לאמון.
    if not os.path.exists(a.control):
        raise SystemExit(f"⛔ קובץ הבקרה חסר: {a.control}. בלי בקרה אין בדיקה.")
    c = judge(a.control, key)
    if c.get("voice_gender") != "male":
        raise SystemExit(
            f"⛔ הבדיקה פגומה, לא התוצר. השופט קבע '{c}' על קובץ בקרה גברי ידוע\n"
            f"   ({a.control}). אין להאמין לפסק הדין שלה. לתקן את הבדיקה קודם.")
    print(f"🔑 בקרה עברה: {os.path.basename(a.control)} → male ({c.get('confidence')})")

    files = [f for pat in a.files for f in sorted(glob.glob(pat))] or a.files
    failed = []
    for f in files:
        v = judge(f, key)
        g, conf = v.get("voice_gender"), v.get("confidence")
        ok = (g == "male") or (g == "none" and a.allow_none)
        if not ok:
            failed.append((f, g, conf))
        print(f"  {'✅' if ok else '⛔'} {os.path.basename(f):24s} {g:8s} ({conf})")
        time.sleep(0.4)

    if failed:
        print(f"\n⛔ {len(failed)} קבצים נפסלו — לייצר מחדש. אין קול אישה בשום תוצר.",
              file=sys.stderr)
        for f, g, conf in failed:
            print(f"   {f}: {g} ({conf})", file=sys.stderr)
        sys.exit(1)
    print(f"\n✅ כל {len(files)} הקבצים גבריים. הבקרה עברה, ולכן הפסק תקף.")


if __name__ == "__main__":
    main()
