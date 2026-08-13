#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
heb_ass.py — בניית קובצי ASS עם כתוביות עבריות שמתרנדרות נכון ב-libass.

רקע (נמדד בשלב 2, ראו setup.log):
  libass בסביבה הזאת נבנה עם fribidi ו-harfbuzz, והוא *כן* מיישם bidi:
  ריצת העברית מתהפכת נכון. אבל כיוון-הבסיס של הפסקה נקבע אצלו כ-LTR,
  ולכן סימני פיסוק ניטרליים בקצה השורה (. ! ? :) נוחתים בקצה *הימני*
  במקום השמאלי — כלומר בסוף המשפט מבחינה ויזואלית-לטינית, לא עברית.

הפתרון: לעטוף כל שורה ב-U+202B (RLE) ... U+202C (PDF), שמכריח כיוון-בסיס RTL.
  נמדד ואומת: הנקודה עוברת לקצה השמאלי והאות הראשונה יושבת בקצה הימני.

מה *לא* לעשות: אין להריץ python-bidi/get_display() על הטקסט לפני libass.
  זה גורם להיפוך כפול — נמדד: הנקודה אמנם משמאל, אבל העברית עצמה מתהפכת
  ונקראת הפוך. python-bidi מיועד לרנדררים חסרי bidi; libass כאן אינו כזה.
"""
import json, sys, argparse

RLE, PDF = "\u202B", "\u202C"   # Right-to-Left Embedding / Pop Directional Formatting

def rtl(text: str) -> str:
    """עוטף טקסט עברי בכיוון-בסיס RTL מפורש."""
    return f"{RLE}{text}{PDF}"

def esc(text: str) -> str:
    """בריחה מתווים בעלי משמעות ב-ASS."""
    return (text.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")
                .replace("\r\n", "\\N").replace("\n", "\\N"))

def heb(text: str) -> str:
    """טקסט עברי מוכן לשורת Dialogue: בריחה + כיוון RTL."""
    return rtl(esc(text))

def ts(seconds: float) -> str:
    """שניות -> חותמת זמן ASS (h:mm:ss.cc)."""
    if seconds < 0: seconds = 0.0
    h = int(seconds // 3600); m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h}:{m:02d}:{s:05.2f}"

HEADER = """[Script Info]
; נוצר ע"י tools/heb_ass.py — כיוון-בסיס RTL נכפה ב-U+202B/U+202C
ScriptType: v4.00+
PlayResX: {w}
PlayResY: {h}
WrapStyle: 0
ScaledBorderAndShadow: yes
YCbCr Matrix: TV.709

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, Bold, Italic, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
{styles}

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

# סגנון הבסיס של הפרויקט — זהה למה שאומת בשלב 2
STYLE_HEB = "Style: HeB,Rubik,64,&H00FFFFFF,&H00000000,&H80000000,-1,0,1,4,2,2,60,60,70,177"

def build(events, width=1920, height=1080, styles=(STYLE_HEB,)) -> str:
    """events = [(start_sec, end_sec, text, style_name?)] -> מחרוזת ASS מלאה."""
    out = [HEADER.format(w=width, h=height, styles="\n".join(styles))]
    for ev in events:
        start, end, text = ev[0], ev[1], ev[2]
        style = ev[3] if len(ev) > 3 else "HeB"
        out.append(f"Dialogue: 0,{ts(start)},{ts(end)},{style},,0,0,0,,{heb(text)}\n")
    return "".join(out)

def main():
    p = argparse.ArgumentParser(description="בניית ASS עברי תקין")
    p.add_argument("--json", help='קובץ JSON: [{"start":0,"end":2.5,"text":"..."}]')
    p.add_argument("--text", help="שורה בודדת (לבדיקה מהירה)")
    p.add_argument("--dur", type=float, default=5.0, help="משך שורה בודדת")
    p.add_argument("--out", required=True)
    a = p.parse_args()
    if a.json:
        with open(a.json, encoding="utf-8") as f: data = json.load(f)
        evs = [(d["start"], d["end"], d["text"], d.get("style", "HeB")) for d in data]
    elif a.text:
        evs = [(0.0, a.dur, a.text)]
    else:
        p.error("צריך --json או --text")
    with open(a.out, "w", encoding="utf-8") as f: f.write(build(evs))
    print(f"נכתב: {a.out}  ({len(evs)} שורות)")

if __name__ == "__main__":
    main()
