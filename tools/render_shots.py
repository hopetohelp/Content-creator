#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""render_shots.py — כל שוט ל-MP4 נפרד, עם תנועת מצלמה בפילטרים של ffmpeg.

🔴 **לעולם לא רינדור אחד ארוך.** מעבר מלא על 90 שניות לוקח כאן ~4.2 דקות,
וההפקה דורשת כמה מעברים. סשן שנקטע באמצע רינדור רציף מאבד הכול; סשן
שנקטע אחרי קטע 7 ממשיך מקטע 8. ראו CLAUDE.md פרק 7.

**איך נוצרת התנועה:** אין מודל וידאו בסביבה הזאת. כל שוט הוא סטיל, והתנועה
מגיעה מ-`zoompan` על גרסה מוגדלת פי 2 של הסטיל. ההגדלה המוקדמת היא מה שמונע
את הריצוד ש-`zoompan` מייצר כשהוא מזיז תמונה בגודל המקורי.

הכלי **ניתן להמשכה**: קטע שכבר קיים באורך הנכון מדולג.

שימוש:
    python3 tools/render_shots.py                 # מרנדר את מה שחסר
    python3 tools/render_shots.py --only s12 s13
"""
import argparse, json, os, subprocess, sys

FPS = 30
OUT_DIR = "output/segments"
SHOTLIST = "assets/shots/shotlist.json"
PNG_DIR = "assets/shots"

# מראה אחיד לכל השוטים: הרמה קלה (הפריימים כהים מאוד), רוויה, וגרעין עדין.
# הגרעין הוא מה שמונע מהסטילס להיראות כמו מצגת שקופיות.
LOOK = ("eq=brightness=0.024:saturation=1.10:contrast=1.05,"
        "noise=alls=5:allf=t+u,"
        "unsharp=5:5:0.45:5:5:0.0")


def motion(move, d):
    """מחזיר את ביטויי z/x/y ל-zoompan. d = מספר פריימי הפלט."""
    last = max(d - 1, 1)
    cx, cy = "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"
    p = f"on/{last}"                       # התקדמות 0→1

    if move == "push_in":
        return f"1+0.13*{p}", cx, cy
    if move == "snap_in":                  # זום פנימה חד — רגע של אימפקט
        return f"1.30-0.28*pow({p},0.42)", cx, cy
    if move == "punch":                    # אגרוף קצר ואז התייצבות
        return f"1.20-0.17*pow({p},0.35)", cx, cy
    if move == "hold":                     # כמעט סטטי, רק נשימה
        return f"1+0.035*{p}", cx, cy
    if move == "shake":                    # מצלמת יד
        return (f"1.12+0.03*{p}",
                f"{cx}+16*sin({p}*38)", f"{cy}+12*cos({p}*31)")
    if move == "ken_right":
        return "1.14", f"(iw-iw/zoom)*{p}", cy
    if move == "ken_left":
        return "1.14", f"(iw-iw/zoom)*(1-{p})", cy
    if move == "ken_down":
        return "1.14", cx, f"(ih-ih/zoom)*{p}"
    if move == "ken_up":
        return "1.14", cx, f"(ih-ih/zoom)*(1-{p})"
    if move == "zoom_corner":              # זום אל הפינה שבה יושב המספר האפור
        z = f"1+0.62*pow({p},0.8)"
        return z, "min(max(0.735*iw-(iw/zoom/2),0),iw-iw/zoom)", \
                  "min(max(0.790*ih-(ih/zoom/2),0),ih-ih/zoom)"
    raise SystemExit(f"⛔ תנועה לא מוכרת: {move}")


def render(shot, out):
    dur = shot["end"] - shot["start"]
    d = int(round(dur * FPS))
    z, x, y = motion(shot["move"], d)
    png = os.path.join(PNG_DIR, f"{shot['id']}.png")
    vf = (f"scale=3840:2160,"
          f"zoompan=z='{z}':x='{x}':y='{y}':d={d}:s=1920x1080:fps={FPS},"
          f"{LOOK},setsar=1,format=yuv420p")
    cmd = ["ffmpeg", "-v", "error", "-i", png, "-filter_complex", vf,
           "-frames:v", str(d), "-c:v", "libx264", "-preset", "fast",
           "-crf", "20", "-pix_fmt", "yuv420p", "-r", str(FPS), out, "-y"]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"⛔ {shot['id']} נכשל:\n{r.stderr[:600]}")
    return d


def probe(path):
    """מחזיר (פריימים, שניות). קוד יציאה 0 אינו הוכחה — CLAUDE.md פרק 6."""
    if not os.path.exists(path):
        return 0, 0.0
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0",
         "-show_entries", "stream=nb_read_frames", "-show_entries",
         "format=duration", "-of", "default=nw=1:nk=1", path],
        capture_output=True, text=True).stdout.split()
    try:
        return int(out[0]), float(out[1])
    except (ValueError, IndexError):
        return 0, 0.0


def mean_luma(path):
    """בהירות ממוצעת. פריים שחור לגמרי הוא כישלון גם אם ffmpeg החזיר 0."""
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", path, "-vf",
                        "signalstats,metadata=print:key=lavfi.signalstats.YAVG",
                        "-f", "null", "-"], capture_output=True, text=True).stderr
    vals = [float(l.split("=")[1]) for l in r.splitlines()
            if "lavfi.signalstats.YAVG" in l]
    return sum(vals) / len(vals) if vals else 0.0


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--only", nargs="*")
    p.add_argument("--force", action="store_true")
    a = p.parse_args()

    os.makedirs(OUT_DIR, exist_ok=True)
    shots = json.load(open(SHOTLIST, encoding="utf-8"))

    done = skipped = 0
    for s in shots:
        if a.only and s["id"] not in a.only:
            continue
        out = os.path.join(OUT_DIR, f"{s['id']}.mp4")
        want = int(round((s["end"] - s["start"]) * FPS))
        have, _ = probe(out)
        if not a.force and have == want:
            skipped += 1
            continue
        render(s, out)
        got, dur = probe(out)
        if got != want:
            raise SystemExit(f"⛔ {s['id']}: {got} פריימים במקום {want}")
        luma = mean_luma(out)
        if luma < 3.0:
            raise SystemExit(f"⛔ {s['id']}: בהירות ממוצעת {luma:.1f} — פריים שחור.")
        print(f"  ✅ {s['id']}  {dur:5.2f}s  {got:3d}f  בהירות {luma:5.1f}  {s['move']}")
        done += 1

    print(f"רונדרו {done} קטעים, דולגו {skipped} שכבר היו תקינים.")


if __name__ == "__main__":
    main()
