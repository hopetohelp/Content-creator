#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fetch_image.py — תמונות מ-Pollinations. חינם, בלי מפתח, בלי חשבון.

🔴 **הכלי הזה אינו הנתיב המאושר. לא להשתמש בו בלי לקרוא את הפסקה הזאת.**

הוא נכתב כשב-`CLAUDE.md` היה כתוב "מסלול A" (‏$0, בלי תמונות בתשלום).
**בינתיים main השתנה:** הבעלים אישר **מסלול B**, ובדיקה עצמאית שם מדדה
ש-Pollinations **מחזיר סגנון ציורי ב-1024×576 ומתעלם מהפרמטרים** — כלומר
אינו עומד בדרישת "תמונות ריאליסטיות, צילום ולא ציור". המקור המאושר הוא
`gemini-3.1-flash-image` (Nano Banana). ראו סעיף הוויזואליה ב-`CLAUDE.md`.

הכלי נשמר כגיבוי בלבד — למקרה שאין תקציב או שאין גישה ל-Gemini.
התוצרים שלו יושבים ב-`assets/stills/` ו**אינם מאושרים לקליפ**.

**מה בכל זאת נמדד כאן ושווה לקחת לכלי הבא:** סדר הרכיבים בפרומפט אינו
שרירותי. כשההבעה מופיעה אחרי בלוק הזהות והסגנון, המודל מתעלם ממנה ומחזיר
פורטרט ניטרלי; כשהיא ראשונה, היא נתפסת. אותו דבר לגבי הסביבה — בלי משפט
מפורש על "חדר חשוך בלילה" מתקבל פורטרט אולפן על רקע בהיר.

⚠️ **נמדד:** הוא מחזיר 1024×576 גם כשמבקשים 1920×1080. הכלי מגדיל בעצמו
ל-Full HD ב-ffmpeg. אל תסמכו על הרוחב שביקשתם.

🔴 **נעילת דמות.** אין `seed` שמבטיח פנים זהות, ולכן העקביות נשענת על שני
דברים יחד: **בלוק תיאור זהה מילה במילה** בכל פרומפט (`IDENTITY`), ו-seed
קבוע לכל שוט. בנוסף — לפי הבריף רק ~40% מהשוטים מראים פנים, וזה מה שמוריד
את הסיכון בפועל.

🔴 **הכלל "אין נשים"** נכנס לכל פרומפט אוטומטית (`NEGATIVE`), ונבדק אחר כך
במדידה על הפריימים ב-`qa_clip.py`. פרומפט אינו ערובה.

הכלי **ניתן להמשכה**: תמונה קיימת ותקינה מדולגת.

שימוש:
    python3 tools/fetch_image.py --spec assets/stills/prompts.json --outdir assets/stills
"""
import argparse, io, json, os, subprocess, sys, time, urllib.parse, urllib.request

BASE = "https://image.pollinations.ai/prompt/"
W, H = 1920, 1080

# בלוק הזהות — **זהה מילה במילה בכל שוט**. זו נעילת הדמות.
IDENTITY = ("he wears thick black-framed glasses and a dark grey hoodie, "
            "short messy dark hair, light stubble, late twenties")

# הסביבה. **נמדד:** בלי המשפט הזה במפורש Flux מחזיר פורטרט אולפן על רקע בהיר
# במקום חדר מפתחים חשוך. "cinematic film still" לבדו לא מספיק.
ENVIRONMENT = ("he sits in a completely dark room at night, lit only by the blue "
               "glow of computer monitors behind him, dark background, night")

# האילוץ הקשיח של הפרויקט, בכל פרומפט
NEGATIVE = ("male only, no women, no female characters, no background people, "
            "not a caricature, no text, no watermark")

LOOK = "photorealistic photo, high detail, 35mm"


def build_prompt(scene, with_identity=True):
    """סדר הרכיבים אינו שרירותי. **נמדד:** כשההבעה מופיעה אחרי בלוק הזהות
    והסגנון, Flux מתעלם ממנה ומחזיר פורטרט ניטרלי. ההבעה חייבת להיות ראשונה."""
    parts = [scene]
    if with_identity:
        parts += [IDENTITY, ENVIRONMENT]
    parts += [LOOK, NEGATIVE]
    return ", ".join(parts)


def fetch(prompt, seed, out, retries=4):
    url = (BASE + urllib.parse.quote(prompt, safe="")
           + f"?width={W}&height={H}&seed={seed}&nologo=true&model=flux")
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=240) as r:
                data = r.read()
            if len(data) < 8000:
                raise ValueError(f"תשובה קטנה מדי: {len(data)} bytes")
            tmp = out + ".raw"
            open(tmp, "wb").write(data)
            # ⚠️ מגיע ב-1024x576 — להגדיל ל-Full HD ולחתוך ל-16:9 מדויק
            p = subprocess.run(
                ["ffmpeg", "-v", "error", "-i", tmp, "-vf",
                 f"scale={W}:{H}:force_original_aspect_ratio=increase:flags=lanczos,"
                 f"crop={W}:{H}", "-q:v", "2", out, "-y"], capture_output=True, text=True)
            os.remove(tmp)
            if p.returncode != 0 or not os.path.exists(out):
                raise ValueError(f"ffmpeg נכשל: {p.stderr[:200]}")
            return
        except Exception as e:                      # noqa: BLE001
            last = repr(e)
            time.sleep(2 ** attempt * 2)
    raise SystemExit(f"⛔ הורדת התמונה נכשלה אחרי {retries} ניסיונות: {last}")


def valid(path):
    if not os.path.exists(path) or os.path.getsize(path) < 20000:
        return False
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                          "-show_entries", "stream=width,height", "-of",
                          "default=nw=1:nk=1", path], capture_output=True, text=True)
    return out.stdout.split() == [str(W), str(H)]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--spec", required=True)
    p.add_argument("--outdir", required=True)
    p.add_argument("--force", action="store_true")
    p.add_argument("--only", nargs="*")
    a = p.parse_args()

    spec = json.load(io.open(a.spec, encoding="utf-8"))
    os.makedirs(a.outdir, exist_ok=True)

    made = skipped = 0
    for item in spec:
        if a.only and item["id"] not in a.only:
            continue
        out = os.path.join(a.outdir, f"{item['id']}.jpg")
        if not a.force and valid(out):
            skipped += 1
            continue
        prompt = build_prompt(item["scene"], item.get("identity", True))
        fetch(prompt, item.get("seed", 42), out)
        print(f"  ✅ {item['id']:16s} seed={item.get('seed',42):<6} {out}", flush=True)
        made += 1
        time.sleep(1.5)

    print(f"הורדו {made} תמונות, דולגו {skipped}.")


if __name__ == "__main__":
    main()
