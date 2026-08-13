#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""character.py — הדמות הראשית כ-SVG פרמטרי.

**למה SVG ולא מודל תמונה:** בסביבה הזאת אין GPU, ואין תקציב למודל תמונה
בתשלום (CLAUDE.md פרק 1, מסלול A). אבל זה לא רק פשרה — זה פותר שתי בעיות
שהבריף מגדיר כקריטיות:

1. **עקביות הדמות.** "הדמות זהה בשוט 3 ובשוט 14" הוא הכשל הכי בולט לצופה.
   כאן זה לא סיכון בכלל: זו אותה גאומטריה בדיוק בכל שוט. משתנים רק
   ההבעה והתאורה.
2. **הכלל 'אין נשים'.** דמות שמצוירת ביד לא יכולה לייצר אישה בטעות ברקע.
   האילוץ מתקיים במבנה, לא בבדיקה בדיעבד.

הסגנון הוא פוסטר גרפי עם תאורת קצה — לא ניסיון לריאליזם. ניסיון ריאליזם
ב-SVG נכשל ונראה כמו קריקטורה זולה, וזה בדיוק מה שהבריף אוסר.

הבעות: bored · dread · panic · shout · joy · calm
"""

# הפלטה — נגזרת מהסגנון החזותי: חדר מפתחים כהה, זוהר מסך, לא סייברפאנק גנרי.
SKIN        = "#c98f6a"
SKIN_SHADE  = "#a06b4d"
SKIN_LIGHT  = "#e0a87e"
HAIR        = "#2c2c3c"      # לא שחור: על רקע כהה שיער שחור נבלע והראש נראה קירח
HAIR_HI     = "#43435c"
HOODIE      = "#242832"
HOODIE_DARK = "#181b23"
TEE         = "#2f3644"
FRAME       = "#0d0d12"
RIM_COOL    = "#4de8ff"
RIM_WARM    = "#ff4d6d"

# כל הבעה: גבות, פה, אישון, זיעה, עפעף.
# הפה מוגדר כ-(רוחב, גובה) של פתח + האם נראות שיניים — כך ההבדל בין
# ההבעות הוא **מדיד**, ולא ניואנס של עקומת בזייה שנבלע בפריים.
EXPRESSIONS = {
    "bored": dict(browL=(-6, 2),   browR=(4, 0),    mouth=(46, 0,  0), pupil=(4, 2),  sweat=0, lid=0.34),
    "dread": dict(browL=(-2, 18),  browR=(2, 18),   mouth=(30, 34, 0), pupil=(0, 5),  sweat=1, lid=0.0),
    "panic": dict(browL=(-4, 26),  browR=(4, 26),   mouth=(42, 62, 0), pupil=(0, 7),  sweat=3, lid=0.0),
    "shout": dict(browL=(-12, -14), browR=(12, -14), mouth=(60, 78, 1), pupil=(0, 0), sweat=1, lid=0.0),
    "joy":   dict(browL=(-10, -18), browR=(10, -18), mouth=(74, 52, 1), pupil=(0, 0), sweat=0, lid=0.5),
    "calm":  dict(browL=(-4, 4),   browR=(4, 2),    mouth=(52, 6,  0), pupil=(2, 1),  sweat=0, lid=0.24),
}

MOUTH_CY = 616


def _mouth(spec):
    """פה: קו סגור, או פתח אליפטי עם לשון ושיניים."""
    w, h, teeth = spec
    if h <= 8:                                    # סגור — קו עם עיקול קל
        return (f'<path d="M {500-w} {MOUTH_CY} Q 500 {MOUTH_CY+h+9} {500+w} {MOUTH_CY-2}" '
                f'stroke="#7a3b40" stroke-width="9" fill="none" stroke-linecap="round"/>')
    # השיניים נחתכות לצורת הפה — מלבן לבן חופשי נראה כמו תקלת רינדור
    cid = f"mclip{w}{h}"
    out = (f'<defs><clipPath id="{cid}">'
           f'<ellipse cx="500" cy="{MOUTH_CY}" rx="{w-3}" ry="{h-3}"/></clipPath></defs>'
           f'<ellipse cx="500" cy="{MOUTH_CY}" rx="{w}" ry="{h}" fill="#4a1f26" '
           f'stroke="#33141a" stroke-width="6"/>'
           f'<ellipse cx="500" cy="{MOUTH_CY + h*0.45:.0f}" rx="{w*0.62:.0f}" '
           f'ry="{h*0.42:.0f}" fill="#8d3d4a"/>')       # לשון
    if teeth:
        out += (f'<g clip-path="url(#{cid})">'
                f'<rect x="{500-w:.0f}" y="{MOUTH_CY-h:.0f}" width="{2*w:.0f}" '
                f'height="{h*0.34:.0f}" fill="#f2ede4"/></g>')
    return out


def _sweat(n):
    """טיפות זיעה — סימן הפאניקה. ממוקמות על הרקה, לא על המשקפיים."""
    drops = [(366, 452, 10), (642, 468, 9), (352, 526, 8)]
    return "".join(
        f'<path d="M {x} {y} q -{r} {r*1.5} 0 {r*2.2} q {r} -{r*0.7} 0 -{r*2.2} z" '
        f'fill="#bfefff" opacity="0.9"/>'
        for x, y, r in drops[:n])


def svg(expression="bored", glow="cool", width=1000, height=1000):
    """מחזיר SVG של הדמות. glow: cool (מסך) · warm (אזהרה) · both."""
    e = EXPRESSIONS[expression]
    (bLx, bLy), (bRx, bRy) = e["browL"], e["browR"]
    px, py = e["pupil"]
    rim = {"cool": RIM_COOL, "warm": RIM_WARM, "both": RIM_COOL}[glow]
    rim2 = {"cool": RIM_COOL, "warm": RIM_WARM, "both": RIM_WARM}[glow]

    return f'''<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg"
     width="100%" height="100%" preserveAspectRatio="xMidYMid meet">
  <defs>
    <linearGradient id="skinG" x1="0" y1="0" x2="1" y2="0.3">
      <stop offset="0" stop-color="{SKIN_SHADE}"/>
      <stop offset="0.45" stop-color="{SKIN}"/>
      <stop offset="1" stop-color="{SKIN_LIGHT}"/>
    </linearGradient>
    <linearGradient id="hoodG" x1="0" y1="0" x2="0.4" y2="1">
      <stop offset="0" stop-color="{HOODIE}"/>
      <stop offset="1" stop-color="{HOODIE_DARK}"/>
    </linearGradient>
    <linearGradient id="lensG" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="{rim}" stop-opacity="0.42"/>
      <stop offset="0.5" stop-color="#0b1a22" stop-opacity="0.30"/>
      <stop offset="1" stop-color="{rim2}" stop-opacity="0.32"/>
    </linearGradient>
    <filter id="soft"><feGaussianBlur stdDeviation="7"/></filter>
    <filter id="softer"><feGaussianBlur stdDeviation="20"/></filter>
  </defs>

  <!-- הילת המסך מאחורי הראש — מפרידה את הדמות מהרקע -->
  <ellipse cx="500" cy="470" rx="330" ry="360" fill="{rim}" opacity="0.09" filter="url(#softer)"/>

  <!-- כתפיים והוד -->
  <path d="M 130 1000 Q 150 800 300 726 Q 400 686 500 682 Q 600 686 700 726
           Q 850 800 870 1000 Z" fill="url(#hoodG)"/>
  <!-- ההוד המקומט מאחורי הצוואר -->
  <path d="M 318 742 Q 400 700 500 696 Q 600 700 682 742 Q 640 792 500 796
           Q 360 792 318 742 Z" fill="{HOODIE_DARK}"/>
  <!-- חולצת טי מציצה מהרוכסן -->
  <path d="M 432 720 Q 500 760 568 720 L 590 830 Q 500 872 410 830 Z" fill="{TEE}"/>
  <!-- שרוכי ההוד -->
  <path d="M 452 742 L 444 856" stroke="#8d94a6" stroke-width="9" stroke-linecap="round" fill="none"/>
  <path d="M 548 742 L 558 848" stroke="#8d94a6" stroke-width="9" stroke-linecap="round" fill="none"/>
  <circle cx="443" cy="862" r="8" fill="#6f7686"/><circle cx="559" cy="854" r="8" fill="#6f7686"/>

  <!-- אוזניות על הצוואר -->
  <path d="M 356 706 Q 500 634 644 706" stroke="#15161c" stroke-width="26"
        fill="none" stroke-linecap="round"/>
  <rect x="322" y="676" width="58" height="80" rx="22" fill="#1d1f27"/>
  <rect x="620" y="676" width="58" height="80" rx="22" fill="#1d1f27"/>
  <rect x="330" y="690" width="16" height="52" rx="8" fill="{rim}" opacity="0.5"/>

  <!-- צוואר -->
  <path d="M 434 596 L 434 712 Q 500 744 566 712 L 566 596 Z" fill="{SKIN_SHADE}"/>

  <!-- ראש -->
  <path d="M 348 402 Q 348 262 500 262 Q 652 262 652 402 L 652 500
           Q 652 640 500 668 Q 348 640 348 500 Z" fill="url(#skinG)"/>
  <!-- אוזניים -->
  <ellipse cx="346" cy="474" rx="26" ry="40" fill="{SKIN_SHADE}"/>
  <ellipse cx="654" cy="474" rx="26" ry="40" fill="{SKIN_LIGHT}"/>
  <!-- זיפים על הלסת -->
  <path d="M 372 512 Q 372 634 500 664 Q 628 634 628 512 Q 628 606 500 630
           Q 372 606 372 512 Z" fill="#5d4436" opacity="0.34"/>
  <!-- שיער קצר ומבולגן. קו השיער נמוך — מצח גבוה מדי קורא כקרחת -->
  <path d="M 340 424 Q 326 258 468 246 Q 520 236 566 250 Q 672 268 662 424
           Q 646 386 616 372 Q 560 352 500 356 Q 424 360 384 384 Q 356 398 340 424 Z"
        fill="{HAIR}"/>
  <!-- קוצים — זה מה שהופך "שיער" ל"שיער מבולגן" -->
  <path d="M 398 268 l 24 -34 l 10 30 z M 470 246 l 16 -40 l 22 34 z
           M 552 252 l 30 -32 l 4 34 z M 620 288 l 36 -22 l -8 32 z"
        fill="{HAIR}"/>
  <!-- הבהרה על קודקוד הגולגולת, לא על קו השיער: פס בהיר לאורך המצח נקרא כבנדנה -->
  <path d="M 388 330 Q 456 272 552 278 Q 626 288 656 350 Q 600 306 528 300
           Q 442 294 388 330 Z" fill="{HAIR_HI}" opacity="0.55"/>

  <!-- גבות -->
  <path d="M 400 {462+bLy} q 44 {-20+bLx} 90 {-2+bLx}" stroke="{HAIR}" stroke-width="17"
        fill="none" stroke-linecap="round"/>
  <path d="M 510 {460+bRy} q 46 {-18-bRx} 90 {4-bRx}" stroke="{HAIR}" stroke-width="17"
        fill="none" stroke-linecap="round"/>

  <!-- עיניים -->
  <ellipse cx="443" cy="514" rx="27" ry="{20 - e['lid']*11:.1f}" fill="#f4f1ea"/>
  <ellipse cx="557" cy="514" rx="27" ry="{20 - e['lid']*11:.1f}" fill="#f4f1ea"/>
  <circle cx="{443+px}" cy="{514+py}" r="11" fill="#20252e"/>
  <circle cx="{557+px}" cy="{514+py}" r="11" fill="#20252e"/>
  <circle cx="{446+px}" cy="{510+py}" r="4" fill="{rim}" opacity="0.9"/>
  <circle cx="{560+px}" cy="{510+py}" r="4" fill="{rim}" opacity="0.9"/>

  <!-- משקפיים — מסגרת מרובעת עבה. פריט הזיהוי המרכזי של הדמות -->
  <rect x="386" y="476" width="116" height="80" rx="15" fill="url(#lensG)"
        stroke="{FRAME}" stroke-width="11"/>
  <rect x="498" y="476" width="116" height="80" rx="15" fill="url(#lensG)"
        stroke="{FRAME}" stroke-width="11"/>
  <path d="M 502 508 L 498 508" stroke="{FRAME}" stroke-width="11"/>
  <path d="M 386 496 L 342 486" stroke="{FRAME}" stroke-width="11" stroke-linecap="round"/>
  <path d="M 614 496 L 658 486" stroke="{FRAME}" stroke-width="11" stroke-linecap="round"/>
  <!-- השתקפות המסך על העדשות — זה מה שמוכיח שהוא מול מסך -->
  <path d="M 400 542 l 30 -50 l 18 0 l -30 50 z" fill="{rim}" opacity="0.34"/>
  <path d="M 512 542 l 30 -50 l 18 0 l -30 50 z" fill="{rim}" opacity="0.34"/>

  <!-- אף -->
  <path d="M 498 540 Q 486 578 504 584" stroke="{SKIN_SHADE}" stroke-width="9"
        fill="none" stroke-linecap="round"/>

  <!-- פה -->
  {_mouth(e['mouth'])}

  {_sweat(e['sweat'])}

  <!-- תאורת קצה: קר מצד אחד, חם מהשני. זה מה שנותן את התחושה הקולנועית -->
  <path d="M 652 402 L 652 500 Q 652 640 500 668" stroke="{rim}" stroke-width="10"
        fill="none" opacity="0.65" filter="url(#soft)"/>
  <path d="M 348 402 Q 348 262 500 262" stroke="{rim2}" stroke-width="9"
        fill="none" opacity="0.42" filter="url(#soft)"/>
  <path d="M 700 726 Q 850 800 870 1000" stroke="{rim}" stroke-width="9"
        fill="none" opacity="0.38" filter="url(#soft)"/>
</svg>'''


if __name__ == "__main__":
    import sys
    exp = sys.argv[1] if len(sys.argv) > 1 else "bored"
    sys.stdout.write(svg(exp, sys.argv[2] if len(sys.argv) > 2 else "cool"))
