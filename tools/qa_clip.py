#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""qa_clip.py — שער ה-QA החוסם על הקליפ המוגמר.

מיישם את הרשימה החוסמת שבסעיף 9 של `מסמכים/2. סיכום שיחה עם קלוד.md`,
בשלוש דרכים שונות — ולא באף אחת מהן "בעין":

1. **מדידה ב-ffprobe/ffmpeg** — משך, זרמים, ‎pix_fmt, פריימים שחורים,
   שקט באודיו.
2. **דגימת פריימים כל 2 שניות + שיפוט של מודל ראייה** — הכלל "אין נשים".
   זו הבדיקה שהבריף מגדיר במפורש כחוסמת.
3. **בדיקת הכתוביות בטקסט** — שאין שורה באנגלית, ושאין `%10` הפוך.

🔑 **קובץ בקרה, כמו בכל בדיקה בריפו:** לשופט נשלח קודם פריים שידוע
שמופיעה בו הדמות. אם הוא מדווח "אין בני אדם בפריים" — **הבדיקה עיוורת,
לא התוצר**, והכלי נופל במקום להכריז שהכול תקין. ראו CLAUDE.md פרק 6.

שימוש:
    python3 tools/qa_clip.py output/final.mp4
"""
import argparse, base64, json, os, re, subprocess, sys, tempfile, time
import urllib.request

MODEL = "gemini-3.1-flash-lite"          # חינם רשמית — תקף גם במסלול A
API = "https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={k}"

PROMPT = ('Look at this video frame. Answer ONLY with JSON: '
          '{"people_visible": <integer>, "any_female_figure": true|false, '
          '"what_you_see": "<8 words max>"}. '
          'Count any drawn, illustrated or photographic human figure. '
          'Set any_female_figure true if ANY figure reads as a woman or girl, '
          'including on a screen, poster or in the background.')


def sh(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


def probe(path, entries, stream=None):
    cmd = ["ffprobe", "-v", "error"]
    if stream:
        cmd += ["-select_streams", stream]
    cmd += ["-show_entries", entries, "-of", "default=nw=1:nk=1", path]
    return sh(cmd).stdout.split()


BRIGHT_LUMA = 60          # מעליו פיקסל נחשב "תוכן", לא רקע חדר חשוך
MIN_BRIGHT_RATIO = 0.0004  # 0.04% מהפריים — סמן בודד עובר, פריים ריק לא
MIN_PEAK = 80


def _frame_stats(video, fps=2.0, size=320):
    """מחזיר [(זמן, שיא לומה, שיעור פיקסלים בהירים)] לפריימים דגומים."""
    import numpy as np
    from PIL import Image
    with tempfile.TemporaryDirectory() as td:
        sh(["ffmpeg", "-v", "error", "-i", video, "-vf",
            f"fps={fps},scale={size}:-1", os.path.join(td, "f%05d.png"), "-y"])
        out = []
        for i, fn in enumerate(sorted(os.listdir(td))):
            a = np.asarray(Image.open(os.path.join(td, fn)).convert("L"), dtype=float)
            out.append((i / fps, float(a.max()), float((a > BRIGHT_LUMA).mean())))
        return out


def frame_deadness(video):
    """זמני פריימים שאין בהם תוכן בהיר כלל. כולל אימות עצמי על פריים שחור."""
    # 🔑 בקרה: פריים שחור אמיתי חייב להיתפס. בדיקה שלא תופסת אותו חסרת ערך.
    with tempfile.TemporaryDirectory() as td:
        blk = os.path.join(td, "black.mp4")
        sh(["ffmpeg", "-v", "error", "-f", "lavfi", "-i",
            "color=c=black:s=320x180:d=1:r=2", "-pix_fmt", "yuv420p", blk, "-y"])
        ctrl = _frame_stats(blk)
        if not ctrl or any(p >= MIN_PEAK or r >= MIN_BRIGHT_RATIO for _, p, r in ctrl):
            raise SystemExit("⛔ הבדיקה פגומה: גלאי הפריימים המתים לא זיהה פריים שחור מלא.")

    stats = _frame_stats(video)
    dead = [t for t, peak, ratio in stats
            if peak < MIN_PEAK and ratio < MIN_BRIGHT_RATIO]
    return dead, len(stats)


def judge_frame(path, key, retries=4):
    b64 = base64.b64encode(open(path, "rb").read()).decode("ascii")
    body = json.dumps({"contents": [{"parts": [
        {"inline_data": {"mime_type": "image/jpeg", "data": b64}},
        {"text": PROMPT}]}]}).encode("utf-8")
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(API.format(m=MODEL, k=key), data=body,
                                         headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=180) as r:
                data = json.loads(r.read().decode("utf-8"))
            t = data["candidates"][0]["content"]["parts"][0]["text"].strip()
            t = t.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            return json.loads(t)
        except Exception as e:                     # noqa: BLE001
            last = repr(e)
            time.sleep(2 ** attempt)
    raise SystemExit(f"⛔ שופט הפריימים נכשל על {path}: {last}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("video")
    p.add_argument("--subs", default="subs/clip.ass")
    p.add_argument("--every", type=float, default=2.0)
    p.add_argument("--skip-vision", action="store_true")
    a = p.parse_args()

    fails, notes = [], []

    def check(ok, label, detail=""):
        print(f"  {'✅' if ok else '⛔'} {label}" + (f"  — {detail}" if detail else ""))
        if not ok:
            fails.append(label)

    print("── מדידה על הקובץ ──")
    dur = float(probe(a.video, "format=duration")[0])
    check(85.0 <= dur <= 95.0, "משך 85–95 שניות", f"{dur:.2f}s")

    v = probe(a.video, "stream=codec_name,width,height,pix_fmt,r_frame_rate", "v:0")
    au = probe(a.video, "stream=codec_name,channels,sample_rate", "a:0")
    check(bool(v), "קיים זרם וידאו", " ".join(v))
    check(bool(au), "קיים זרם אודיו", " ".join(au))
    check(len(v) > 3 and v[3] == "yuv420p", "pix_fmt = yuv420p", v[3] if len(v) > 3 else "?")
    check(len(v) > 2 and (v[1], v[2]) == ("1920", "1080"), "רזולוציה 1920x1080",
          f"{v[1]}x{v[2]}" if len(v) > 2 else "?")

    # ── פריימים מתים ──
    # 🔴 **לא להשתמש כאן ב-blackdetect.** נמדד: הוא סימן ככישלון גם את השוט
    # שבו הזום נוחת על תג "tokens 10%" קריא לגמרי, וגם את תיבת הדממה שבה
    # רואים שני מסכים, שולחן וסמן. הסיבה: ברירת המחדל שלו היא "98% מהפיקסלים
    # מתחת ללומה 25", והקליפ הזה **כהה בכוונה** — התוכן חי בשטח קטן ובהיר
    # בתוך חדר חשוך. הבדיקה הייתה פגומה, לא התוצר. (CLAUDE.md פרק 6 — זו
    # הפעם החמישית בריפו הזה.)
    #
    # מה שבאמת מגדיר פריים מת: **אין בו תוכן בהיר בכלל.** את זה מודדים.
    dead, checked = frame_deadness(a.video)
    check(not dead, f"אין פריימים מתים ({checked} פריימים נמדדו)",
          f"{len(dead)} חשודים" + (f" ב-{dead[0]:.1f}s" if dead else ""))

    # אודיו לא שקט
    vd = sh(["ffmpeg", "-hide_banner", "-i", a.video, "-af", "volumedetect",
             "-f", "null", "-"]).stderr
    mean = next((float(l.split("mean_volume:")[1].split()[0])
                 for l in vd.splitlines() if "mean_volume:" in l), -99.0)
    check(mean > -40.0, "האודיו אינו שקט", f"mean {mean:.1f} dB")

    print("\n── כתוביות ──")
    txt = open(a.subs, encoding="utf-8").read()
    dlg = [l.split(",,", 1)[1] if ",," in l else l
           for l in txt.splitlines() if l.startswith("Dialogue:")]
    check(bool(dlg), "יש כרטיסי כתובית", f"{len(dlg)} כרטיסים")
    latin = [d for d in dlg if re.search(r"[A-Za-z]{3,}", d)]
    check(not latin, "אין שורת כתובית באנגלית", f"{len(latin)} חריגות")
    heb_cards = [d for d in dlg if re.search(r"[֐-׿]", d)]
    check(len(heb_cards) == len(dlg), "כל הכרטיסים בעברית",
          f"{len(heb_cards)}/{len(dlg)}")
    check("%10" not in txt and "%1 " not in txt, "אין אחוז הפוך (%10) בכתוביות")
    check(all("‫" in d and "‬" in d for d in dlg),
          "כל שורה עטופה בכיוון RTL")
    long_lines = [seg for d in dlg for seg in d.replace("‫", "")
                  .replace("‬", "").split("\\N") if len(seg.strip()) > 38]
    check(not long_lines, "אין שורה מעל 38 תווים", f"{len(long_lines)} חריגות")

    if a.skip_vision:
        print("\n(דילוג על בדיקת הראייה לפי בקשה)")
    else:
        print(f"\n── 'אין נשים': דגימת פריים כל {a.every:.0f} שניות ──")
        key = os.environ.get("GEMINI_API_KEY")
        if not key:
            raise SystemExit("⛔ אין GEMINI_API_KEY — אי אפשר להריץ את הבדיקה החוסמת.")
        with tempfile.TemporaryDirectory() as td:
            sh(["ffmpeg", "-v", "error", "-i", a.video, "-vf",
                f"fps=1/{a.every},scale=960:-1", "-q:v", "3",
                os.path.join(td, "f%03d.jpg"), "-y"])
            frames = sorted(os.listdir(td))
            if not frames:
                raise SystemExit("⛔ לא חולצו פריימים.")

            # 🔑 בקרה: פריים שידוע שמופיעה בו הדמות
            ctrl = "assets/shots/s11.png"
            cj = os.path.join(td, "ctrl.jpg")
            sh(["ffmpeg", "-v", "error", "-i", ctrl, "-vf", "scale=960:-1",
                "-q:v", "3", cj, "-y"])
            c = judge_frame(cj, key)
            if int(c.get("people_visible", 0)) < 1:
                raise SystemExit(
                    f"⛔ הבדיקה עיוורת, לא התוצר: השופט לא זיהה אדם בפריים בקרה\n"
                    f"   שבו הדמות מופיעה במרכז ({ctrl}) → {c}.\n"
                    "   אין להאמין לפסק הדין שלה. לתקן את הבדיקה קודם.")
            if c.get("any_female_figure"):
                raise SystemExit(
                    f"⛔ השופט קבע 'אישה' על הדמות הגברית של הפרויקט → {c}. הבדיקה פגומה.")
            print(f"  🔑 בקרה עברה: זוהו {c.get('people_visible')} אנשים, "
                  f"נשים: {c.get('any_female_figure')} — «{c.get('what_you_see')}»")

            flagged, seen_people = [], 0
            for i, fn in enumerate(frames):
                r = judge_frame(os.path.join(td, fn), key)
                t = a.every * i
                seen_people += int(r.get("people_visible", 0) or 0)
                if r.get("any_female_figure"):
                    flagged.append((t, r))
                    print(f"    ⛔ {t:5.1f}s  {r}")
                time.sleep(0.35)
            check(not flagged, f"אין נשים באף פריים ({len(frames)} פריימים נבדקו)",
                  f"{len(flagged)} חריגות")
            notes.append(f"סה\"כ דמויות שזוהו על פני {len(frames)} פריימים: {seen_people}")

    print("\n" + "=" * 60)
    for n in notes:
        print("   " + n)
    if fails:
        print(f"⛔ נכשלו {len(fails)} סעיפים: {', '.join(fails)}")
        sys.exit(1)
    print("✅ כל סעיפי ה-QA עברו.")


if __name__ == "__main__":
    main()
