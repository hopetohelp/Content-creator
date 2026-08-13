#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
בדיקת אמת ל-RTL: האם libass מיישם את אלגוריתם ה-bidi, או מסדר גליפים בסדר לוגי?

השיטה עוקפת לגמרי את הצורך "לקרוא" עברית — שהיא בדיוק נקודת הכשל של בדיקה חזותית:
1. מרנדרים את המחרוזת  "ABC אבג".  התו החזק הראשון הוא לטיני, לכן כיוון הפסקה LTR.
   - אם bidi מופעל: ריצת העברית מתהפכת בתוך הפסקה  ->  הגליף הימני-קיצוני הוא  א
   - אם bidi לא מופעל: הגליפים בסדר לוגי               ->  הגליף הימני-קיצוני הוא  ג
2. מרנדרים בנפרד  א  ו-ג  כרפרנס, חותכים כל אחד "צמוד", ומשווים פיקסלים
   לגליף הימני-קיצוני של המחרוזת המורכבת.
עברית אינה כותב מחבר, ולכן הביטמאפ של אות בודדת זהה לביטמאפ שלה בתוך מילה.
"""
import subprocess, sys, tempfile, os
import numpy as np
from PIL import Image

ASS_TMPL = """[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 2

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, Bold, Italic, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: P,{font},96,&H00FFFFFF,&H00000000,&H00000000,0,0,1,0,0,7,60,60,60,177

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:00.00,0:00:05.00,P,,0,0,0,,{text}
"""

def render(text, font, fontsdir):
    ass = tempfile.NamedTemporaryFile("w", suffix=".ass", delete=False, encoding="utf-8")
    ass.write(ASS_TMPL.format(font=font, text=text)); ass.close()
    png = tempfile.mktemp(suffix=".png")
    subprocess.run(["ffmpeg","-hide_banner","-loglevel","error","-y",
        "-f","lavfi","-i","color=c=0x000000:s=1920x1080:d=1",
        "-vf",f"subtitles={ass.name}:fontsdir={fontsdir}",
        "-frames:v","1","-update","1",png], check=True)
    a = np.asarray(Image.open(png).convert("L")).astype(np.uint8)
    os.unlink(ass.name); os.unlink(png)
    return a > 60

def tight(mask):
    ys, xs = np.nonzero(mask)
    return mask[ys.min():ys.max()+1, xs.min():xs.max()+1]

def groups(mask, min_gap=6):
    """מפצל למקבצי-עמודות (גליפים/מילים) לפי רווחים אנכיים ריקים."""
    col = mask.sum(0) > 0
    out, start = [], None
    gap = 0
    for x, v in enumerate(col):
        if v:
            if start is None: start = x
            gap = 0
        elif start is not None:
            gap += 1
            if gap >= min_gap:
                out.append((start, x - gap)); start = None
    if start is not None: out.append((start, len(col)-1))
    return out

def score(a, b):
    """דמיון 0..1 בין שני ביטמאפים צמודים (מיושרים לפי גודל המשותף)."""
    h, w = min(a.shape[0], b.shape[0]), min(a.shape[1], b.shape[1])
    if h == 0 or w == 0: return 0.0
    A, B = a[:h,:w], b[:h,:w]
    union = (A | B).sum()
    shape_pen = abs(a.shape[0]-b.shape[0]) + abs(a.shape[1]-b.shape[1])
    return ((A & B).sum() / union if union else 0.0) * (1.0 / (1 + 0.08*shape_pen))

def probe(font="Rubik", fontsdir="./fonts"):
    print(f"=== בדיקת bidi עבור הפונט: {font} ===")
    ref_alef  = tight(render("א", font, fontsdir))
    ref_gimel = tight(render("ג", font, fontsdir))
    print(f"  רפרנס א : {ref_alef.shape[1]}x{ref_alef.shape[0]} px")
    print(f"  רפרנס ג : {ref_gimel.shape[1]}x{ref_gimel.shape[0]} px")

    comp = render("ABC אבג", font, fontsdir)
    g = groups(comp)
    print(f"  'ABC אבג' התפצל ל-{len(g)} מקבצים: {g}")
    x0, x1 = g[-1]                       # המקבץ הימני-קיצוני
    rightmost = tight(comp[:, x0:x1+1])
    # בתוך המקבץ הימני (מילה עברית) — קח את הגליף הימני-קיצוני
    sub = groups(comp[:, x0:x1+1], min_gap=2)
    if len(sub) > 1:
        sx0, sx1 = sub[-1]
        rightmost = tight(comp[:, x0+sx0:x0+sx1+1])
    print(f"  הגליף הימני-קיצוני: {rightmost.shape[1]}x{rightmost.shape[0]} px")

    s_alef, s_gimel = score(rightmost, ref_alef), score(rightmost, ref_gimel)
    print(f"  דמיון ל-א : {s_alef:.3f}")
    print(f"  דמיון ל-ג : {s_gimel:.3f}")
    print()
    if s_alef > s_gimel:
        print("  ✅ הגליף הימני-קיצוני הוא א = האות הלוגית הראשונה של 'אבג'.")
        print("     ==> libass הפך את ריצת העברית. אלגוריתם ה-bidi פועל.")
        return True
    else:
        print("  ❌ הגליף הימני-קיצוני הוא ג = האות הלוגית האחרונה.")
        print("     ==> אין bidi. libass מסדר גליפים בסדר לוגי. נדרש python-bidi.")
        return False

if __name__ == "__main__":
    font = sys.argv[1] if len(sys.argv) > 1 else "Rubik"
    sys.exit(0 if probe(font) else 1)
