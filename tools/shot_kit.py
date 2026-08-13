#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""shot_kit.py — שפת העיצוב של הקליפ: רקע, חלונות, טלפון, מדים, שכבת גרפיקה.

**למה כל שוט הוא HTML ולא תמונה ממודל:** מודל תמונה מייצר טרמינל עם טקסט
מעוות ומספרים לא קריאים — וכאן **המספרים הם הבדיחה**. `10%` חייב להיות
`10%` מדויק. ‏HTML נותן את זה דטרמיניסטית, ובחינם. ראו מסמך 6 סעיף 4.

🔴 **הכלל בפרויקט:** טקסט על המסך ⇒ HTML · בן אדם או סצנה ⇒ מודל תמונה.
בסביבה הזאת אין תקציב למודל תמונה, ולכן גם הדמות היא SVG — `character.py`.

🔴 **המילים המודגשות** (10% · TOKENS · BATTERY · 1% · 0%) נבנות כאן, בשכבת
`gfx`, ו**לעולם לא בתוך שורת כתובית עברית**: ערבוב לטיני-עברי שובר bidi
ו-`10%` מתהפך ל-`%10`. ראו CLAUDE.md פרק 5.
"""

# ---- פלטה ----------------------------------------------------------------
BG        = "#08080c"
PANEL     = "#12141c"
PANEL_HI  = "#1a1d28"
LINE      = "#262b38"
TXT       = "#c7cede"
DIM       = "#5d6577"
CYAN      = "#4de8ff"
GREEN     = "#46e58a"
AMBER     = "#ffb347"
RED       = "#ff4d6d"
MONO      = "'JetBrains Mono','JetBrainsMono',monospace"


def base_css():
    """רקע החדר, זוהר המסך, ויניטה וגרעין — הבסיס הקולנועי לכל שוט."""
    return f"""
*{{margin:0;padding:0;box-sizing:border-box}}
html,body{{width:1920px;height:1080px;overflow:hidden;background:{BG};
  font-family:{MONO};color:{TXT};-webkit-font-smoothing:antialiased}}
.stage{{position:relative;width:1920px;height:1080px;overflow:hidden}}
/* זוהר המסך — מה שהופך "רקע שחור" ל"חדר מפתחים חשוך" */
.stage::before{{content:'';position:absolute;inset:0;z-index:0;
  background:
   radial-gradient(1100px 720px at 50% 38%, rgba(77,232,255,.14), transparent 62%),
   radial-gradient(760px 560px at 84% 74%, rgba(255,77,109,.09), transparent 64%),
   radial-gradient(620px 480px at 12% 82%, rgba(70,229,138,.06), transparent 66%)}}
/* ויניטה + סריקה: מוסיפות "עדשה" ומונעות מהפריים להיראות כמו שקופית */
.stage::after{{content:'';position:absolute;inset:0;z-index:60;pointer-events:none;
  background:
   repeating-linear-gradient(180deg, rgba(0,0,0,.16) 0 1px, transparent 1px 3px),
   radial-gradient(120% 100% at 50% 50%, transparent 52%, rgba(0,0,0,.72) 100%)}}
.layer{{position:absolute;inset:0;z-index:10}}

/* ---- חלון (טרמינל / IDE / דפדפן) ---- */
.win{{position:absolute;background:{PANEL};border:1px solid {LINE};border-radius:14px;
  box-shadow:0 40px 120px rgba(0,0,0,.75), 0 0 0 1px rgba(77,232,255,.06),
             0 0 90px rgba(77,232,255,.07);overflow:hidden}}
.bar{{height:46px;background:{PANEL_HI};border-bottom:1px solid {LINE};
  display:flex;align-items:center;gap:10px;padding:0 18px}}
.dot{{width:13px;height:13px;border-radius:50%}}
.title{{margin-left:14px;font-size:19px;color:{DIM};letter-spacing:.4px}}
.body{{padding:26px 30px;font-size:26px;line-height:1.62}}
.c-dim{{color:{DIM}}} .c-cy{{color:{CYAN}}} .c-gr{{color:{GREEN}}}
.c-am{{color:{AMBER}}} .c-rd{{color:{RED}}} .b{{font-weight:700}}

/* ---- שכבת הגרפיקה: המילים המודגשות ---- */
.gfx{{position:absolute;z-index:50;font-family:{MONO};font-weight:800;
  letter-spacing:.055em;text-transform:uppercase;white-space:nowrap}}
.gfx.big{{font-size:150px}} .gfx.huge{{font-size:210px}} .gfx.mid{{font-size:92px}}
.glow-cy{{color:#eafcff;text-shadow:0 0 22px {CYAN},0 0 62px rgba(77,232,255,.62)}}
.glow-rd{{color:#fff0f3;text-shadow:0 0 22px {RED},0 0 62px rgba(255,77,109,.6)}}
.glow-am{{color:#fff6e6;text-shadow:0 0 22px {AMBER},0 0 62px rgba(255,179,71,.55)}}
.glow-gr{{color:#eafff4;text-shadow:0 0 22px {GREEN},0 0 62px rgba(70,229,138,.55)}}

/* ---- טלפון ---- */
.phone{{position:absolute;width:430px;height:880px;border-radius:56px;
  background:linear-gradient(160deg,#20242f,#0d0f15);border:3px solid #333a49;
  box-shadow:0 50px 130px rgba(0,0,0,.85),0 0 70px rgba(77,232,255,.1);overflow:hidden}}
.screen{{position:absolute;inset:13px;border-radius:44px;background:#05060a;
  display:flex;flex-direction:column;align-items:center;justify-content:center;gap:30px}}
.notch{{position:absolute;top:16px;left:50%;transform:translateX(-50%);
  width:132px;height:26px;border-radius:14px;background:#05060a;z-index:3}}

/* ---- מד סוללה / טוקנים ---- */
.batt{{position:relative;width:250px;height:116px;border:9px solid {TXT};
  border-radius:16px}}
.batt::after{{content:'';position:absolute;right:-26px;top:32px;width:17px;height:44px;
  background:{TXT};border-radius:0 6px 6px 0}}
.fill{{position:absolute;top:6px;bottom:6px;left:6px;border-radius:7px}}
.meter{{height:34px;border-radius:17px;background:#1b1f2a;overflow:hidden;
  border:1px solid {LINE}}}
.meter>i{{display:block;height:100%;border-radius:17px}}
"""


def win(x, y, w, h, title, body_html, accent=CYAN, z=10, extra=""):
    """חלון תוכנה גנרי. הבסיס לטרמינל, ל-IDE ולדפדפן."""
    return f'''<div class="win" style="left:{x}px;top:{y}px;width:{w}px;height:{h}px;z-index:{z};{extra}">
  <div class="bar">
    <span class="dot" style="background:#ff5f57"></span>
    <span class="dot" style="background:#febc2e"></span>
    <span class="dot" style="background:#28c840"></span>
    <span class="title" style="color:{accent}">{title}</span>
  </div>
  <div class="body">{body_html}</div>
</div>'''


def gfx(text, x, y, size="big", glow="cy", extra=""):
    """מילה מודגשת. אף פעם לא בתוך שורת כתובית עברית."""
    return (f'<div class="gfx {size} glow-{glow}" '
            f'style="left:{x}px;top:{y}px;{extra}">{text}</div>')


def phone(x, y, inner, rot=0, scale=1.0):
    return (f'<div class="phone" style="left:{x}px;top:{y}px;'
            f'transform:rotate({rot}deg) scale({scale});z-index:20">'
            f'<div class="notch"></div><div class="screen">{inner}</div></div>')


def battery(pct, color):
    return (f'<div class="batt"><div class="fill" '
            f'style="width:{max(4, int(2.32*pct))}px;background:{color};'
            f'box-shadow:0 0 26px {color}"></div></div>')


def meter(pct, color, width=760):
    return (f'<div class="meter" style="width:{width}px"><i style="width:{pct}%;'
            f'background:linear-gradient(90deg,{color},{color});'
            f'box-shadow:0 0 26px {color}"></i></div>')


def page(body, css_extra=""):
    return (f'<!doctype html><meta charset="utf-8"><style>{base_css()}{css_extra}</style>'
            f'<div class="stage">{body}</div>')
