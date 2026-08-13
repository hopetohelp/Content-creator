#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_shots.py — מגדיר את רשימת השוטים, כותב HTML, ומצלם ל-PNG.

מקור האמת לרשימת השוטים. כל שוט מתחיל ומסתיים על **גבול תיבה** (1.6 שניות
ב-150 BPM), כי החיתוכים חייבים ליפול על הדופק ולא בין דופקים.

**60% מהשוטים אינם מראים פנים** — מסכים, אובייקטים, ידיים ומדים. זה מוריד
את סיכון העקביות של הדמות ונראה יותר קולנועי (מסמך 2, סעיף 5).

שימוש:
    python3 tools/build_shots.py                # בונה ומצלם את מה שחסר
    python3 tools/build_shots.py --force        # מצלם הכול מחדש
    python3 tools/build_shots.py --only s07 s12
"""
import argparse, json, os, subprocess, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from character import svg as char                                   # noqa: E402
from shot_kit import (AMBER, CYAN, DIM, GREEN, LINE, RED, TXT,      # noqa: E402
                      battery, gfx, meter, page, phone, win)

HTML_DIR = "assets/shots/html"
PNG_DIR = "assets/shots"


def person(expr, glow, left, top, w, z=15, extra=""):
    return (f'<div style="position:absolute;left:{left}px;top:{top}px;width:{w}px;'
            f'z-index:{z};{extra}">{char(expr, glow)}</div>')


def code_lines(rows):
    out = []
    for n, (cls, txt) in enumerate(rows, 1):
        out.append(f'<div><span class="c-dim" style="display:inline-block;width:56px;'
                   f'text-align:right;margin-right:26px">{n}</span>'
                   f'<span class="{cls}">{txt}</span></div>')
    return "".join(out)


def desk(extra_glow=""):
    """שולחן חשוך עם שני מסכים — הרקע החוזר של החדר."""
    return f'''<div style="position:absolute;left:0;top:640px;width:1920px;height:440px;
       background:linear-gradient(180deg,#0d1017,#05060a);border-top:1px solid #1c2130;z-index:5"></div>
    <div style="position:absolute;left:120px;top:250px;width:520px;height:330px;border-radius:10px;
       background:#0b0e15;border:2px solid #1e2432;box-shadow:0 0 80px rgba(77,232,255,.13);z-index:6;
       {extra_glow}"></div>
    <div style="position:absolute;left:1290px;top:250px;width:520px;height:330px;border-radius:10px;
       background:#0b0e15;border:2px solid #1e2432;box-shadow:0 0 80px rgba(255,77,109,.1);z-index:6"></div>'''


# ─────────────────────────────────────────────────────────────────────────────
# רשימת השוטים. start/end על גבולות תיבה של 1.6 שניות.
# move = תנועת ffmpeg שתופעל בשלב הרינדור.
# ─────────────────────────────────────────────────────────────────────────────
def shots():
    S = []
    def add(sid, start, end, body, move, note):
        S.append(dict(id=sid, start=start, end=end, html=page(body), move=move, note=note))

    # ── פתיחה קרה ───────────────────────────────────────────────────────────
    add("s01", 0.0, 3.2,
        desk() + phone(745, 110, f'''{battery(10, RED)}
          <div style="font-size:86px;font-weight:800;color:{RED}">10%</div>
          <div style="font-size:30px;color:{DIM};letter-spacing:.16em">BATTERY</div>''')
        + gfx("10% BATTERY", 560, 900, "mid", "rd"),
        "push_in", "טלפון: עשרה אחוז סוללה")

    add("s02", 3.2, 6.4,
        desk() + win(300, 190, 1320, 700, "claude-agent — session", f'''
          {code_lines([("c-dim","$ agent run --task refactor"),
                       ("c-gr","✓ 41 files analyzed"),
                       ("c-gr","✓ patch applied"),
                       ("c-dim","  streaming response…")])}
          <div style="margin-top:44px;color:{DIM};font-size:23px;letter-spacing:.1em">TOKEN BUDGET</div>
          <div style="margin-top:14px">{meter(10, RED, 1180)}</div>
          <div style="margin-top:20px;font-size:70px;font-weight:800;color:{RED}">10% remaining</div>''',
          accent=RED)
        + gfx("10% TOKENS", 560, 930, "mid", "rd"),
        "push_in", "מסך: עשרה אחוז טוקנים")

    add("s03", 6.4, 8.0,
        desk() + person("dread", "warm", 610, 60, 700) ,
        "snap_in", "קלוז-אפ: אוי לא")

    add("s04", 8.0, 9.6,
        desk("box-shadow:0 0 140px rgba(77,232,255,.4)")
        + person("bored", "cool", 660, 250, 600, z=8)
        + gfx("TEN PERCENT", 415, 120, "big", "cy"),
        "shake", "כניסת הביט — כרטיס פתיחה")

    # ── בית 1: סוללה ────────────────────────────────────────────────────────
    add("s05", 9.6, 12.8,
        desk() + phone(745, 110, f'''{battery(10, RED)}
          <div style="font-size:72px;font-weight:800;color:{RED}">10%</div>
          <div style="width:300px;margin-top:10px">{meter(10, RED, 300)}</div>'''),
        "ken_left", "פס אדום בפינה")

    add("s06", 12.8, 16.0,
        desk() + f'''<div style="position:absolute;left:430px;top:330px;width:1060px;
          background:rgba(24,27,36,.97);border:1px solid {LINE};border-radius:26px;
          padding:44px 52px;z-index:25;box-shadow:0 40px 120px rgba(0,0,0,.8)">
          <div style="display:flex;align-items:center;gap:22px">
            <div style="width:64px;height:64px;border-radius:16px;background:{RED};
              display:flex;align-items:center;justify-content:center;font-size:38px">⚡</div>
            <div style="font-size:38px;font-weight:700;color:{TXT}">Low Battery</div>
          </div>
          <div style="margin-top:26px;font-size:32px;color:{DIM}">
            10% of battery remaining. You may want to plug in.</div>
          <div style="margin-top:34px;display:flex;gap:20px">
            <div style="padding:16px 40px;border-radius:14px;background:#222736;
              font-size:26px;color:{DIM}">Low Power Mode</div>
            <div style="padding:16px 40px;border-radius:14px;background:#222736;
              font-size:26px;color:{DIM}">OK</div></div></div>''',
        "push_in", "התראת סוללה חלשה")

    add("s07", 16.0, 19.2,
        f'''<div style="position:absolute;inset:0;background:
           radial-gradient(700px 460px at 50% 62%, rgba(77,232,255,.1), transparent 66%)"></div>
        <svg viewBox="0 0 1920 1080" style="position:absolute;inset:0;z-index:12">
          <path d="M 230 880 C 520 700, 700 1010, 980 830 S 1450 690, 1700 800"
                stroke="#2a3040" stroke-width="26" fill="none" stroke-linecap="round"/>
          <path d="M 230 880 C 520 700, 700 1010, 980 830 S 1450 690, 1700 800"
                stroke="#3b4356" stroke-width="12" fill="none" stroke-linecap="round"/>
          <rect x="1672" y="770" width="86" height="58" rx="9" fill="#4a5468"/>
          <rect x="1748" y="784" width="26" height="12" rx="3" fill="{CYAN}" opacity=".8"/>
          <rect x="196" y="852" width="70" height="56" rx="10" fill="#4a5468"/>
        </svg>
        <div style="position:absolute;left:0;top:660px;width:1920px;height:420px;
          background:linear-gradient(180deg,#0a0d13,#05060a);z-index:6"></div>''',
        "ken_right", "כבל זרוק על הרצפה")

    add("s08", 19.2, 22.4,
        desk() + f'''<div style="position:absolute;left:660px;top:340px;width:600px;height:330px;
          border-radius:34px;background:linear-gradient(150deg,#2b3140,#141821);
          border:2px solid #39415400;box-shadow:0 40px 110px rgba(0,0,0,.8);z-index:22">
          <div style="position:absolute;left:44px;top:52px;font-size:30px;color:{DIM};
            letter-spacing:.2em">POWER BANK</div>
          <div style="position:absolute;left:44px;top:120px;display:flex;gap:14px">
            <span style="width:26px;height:26px;border-radius:50%;background:{GREEN}"></span>
            <span style="width:26px;height:26px;border-radius:50%;background:#2c3242"></span>
            <span style="width:26px;height:26px;border-radius:50%;background:#2c3242"></span>
            <span style="width:26px;height:26px;border-radius:50%;background:#2c3242"></span></div>
          <div style="position:absolute;left:44px;top:200px;font-size:26px;color:#6b7488">
            1 of 4 bars</div>
          <div style="position:absolute;right:46px;bottom:46px;font-size:24px;color:#525b6e">
            purchased 2021</div></div>''',
        "ken_up", "מטען נייד ישן")

    add("s09", 22.4, 25.6,
        desk() + win(430, 250, 1060, 560, "settings — battery", f'''
          <div style="font-size:34px;color:{TXT};margin-bottom:36px">Low Power Mode</div>
          <div style="display:flex;align-items:center;justify-content:space-between">
            <span style="font-size:29px;color:{DIM}">Reduce background activity</span>
            <span style="width:110px;height:56px;border-radius:28px;background:{GREEN};
              position:relative"><i style="position:absolute;right:5px;top:5px;width:46px;
              height:46px;border-radius:50%;background:#0b0e15;display:block"></i></span></div>
          <div style="margin-top:40px;display:flex;align-items:center;justify-content:space-between">
            <span style="font-size:29px;color:{DIM}">Dim display</span>
            <span style="width:110px;height:56px;border-radius:28px;background:{GREEN};
              position:relative"><i style="position:absolute;right:5px;top:5px;width:46px;
              height:46px;border-radius:50%;background:#0b0e15;display:block"></i></span></div>
          <div style="margin-top:56px">{meter(10, AMBER, 940)}</div>''', accent=AMBER),
        "push_in", "מצב חיסכון בסוללה")

    add("s10", 25.6, 28.8,
        desk() + f'''<div style="position:absolute;left:460px;top:400px;width:1000px;z-index:24">
          <div style="font-size:30px;color:{DIM};letter-spacing:.2em;margin-bottom:26px">BRIGHTNESS</div>
          {meter(6, "#6f7789", 1000)}
          <div style="margin-top:30px;font-size:26px;color:#3f4757">nearly dark — still fine</div></div>
        <div style="position:absolute;inset:0;background:rgba(0,0,0,.5);z-index:23"></div>''',
        "ken_down", "בהירות מונמכת")

    add("s11", 28.8, 32.0,
        desk() + person("bored", "cool", 640, 130, 660)
        + f'''<div style="position:absolute;right:120px;bottom:150px;font-size:30px;
          color:{DIM};z-index:30">// still working</div>''',
        "ken_left", "הוא ממשיך לעבוד, אדיש")

    # ── הוק קצר ─────────────────────────────────────────────────────────────
    add("s12", 32.0, 35.2,
        f'''<div style="position:absolute;inset:0;background:
          radial-gradient(760px 620px at 50% 46%, rgba(70,229,138,.14), transparent 66%)"></div>
        <div style="position:absolute;left:835px;top:250px;z-index:20">{battery(10, GREEN)}</div>'''
        + gfx("10%", 800, 430, "huge", "gr")
        + gfx("BATTERY", 700, 720, "mid", "gr"),
        "punch", "עשרה אחוז סוללה — אני אשרוד")

    add("s13", 35.2, 38.4,
        f'''<div style="position:absolute;inset:0;background:
          radial-gradient(760px 620px at 50% 46%, rgba(255,77,109,.17), transparent 66%)"></div>
        <div style="position:absolute;left:580px;top:270px;z-index:20">{meter(10, RED, 760)}</div>'''
        + gfx("10%", 800, 430, "huge", "rd")
        + gfx("TOKENS", 740, 720, "mid", "rd"),
        "punch", "עשרה אחוז טוקנים — בקושי חי")

    # ── בית 2: טוקנים ───────────────────────────────────────────────────────
    add("s14", 38.4, 41.6,
        desk() + win(210, 170, 1500, 740, "main.py — agent session", code_lines([
            ("c-cy", "def apply_patch(files):"),
            ("c-dim", "    # agent is writing this"),
            ("c-gr", "    for f in files:"),
            ("c-gr", "        f.rewrite(plan[f])"),
            ("c-gr", "    return commit(files)"),
            ("c-dim", ""),
            ("c-am", "▸ agent: refactoring 41 files…"),
            ("c-gr", "▸ 38/41 done"),
        ])),
        "ken_up", "הסוכן עובד, הכל נבנה")

    add("s15", 41.6, 44.8,
        desk() + win(260, 200, 1400, 680, "pytest", code_lines([
            ("c-gr", "tests/test_core.py .......... [ 34%]"),
            ("c-gr", "tests/test_api.py  .......... [ 68%]"),
            ("c-gr", "tests/test_cli.py  .......... [100%]"),
            ("c-dim", ""),
            ("c-gr b", "==== 96 passed in 4.21s ===="),
        ]), accent=GREEN),
        "ken_right", "כל הבדיקות ירוקות")

    add("s16", 44.8, 48.0,
        desk() + win(210, 170, 1500, 740, "main.py — agent session", code_lines([
            ("c-gr", "    return commit(files)"),
            ("c-gr", "▸ 41/41 done"),
            ("c-dim", ""), ("c-dim", ""),
        ])) + f'''<div style="position:absolute;left:1290px;top:820px;font-size:29px;
          color:#4b5365;z-index:40">tokens 10%</div>
        <div style="position:absolute;left:1258px;top:806px;width:250px;height:62px;
          border:2px solid {AMBER};border-radius:10px;z-index:39;opacity:.55"></div>''',
        "zoom_corner", "מספר אפור קטן בפינה")

    add("s17", 48.0, 51.2,
        f'''<div style="position:absolute;inset:0;background:
          radial-gradient(900px 700px at 50% 50%, rgba(255,179,71,.2), transparent 68%)"></div>
        <div style="position:absolute;left:580px;top:600px;z-index:22">{meter(10, AMBER, 760)}</div>'''
        + gfx("TOKEN BUDGET", 555, 300, "mid", "am")
        + gfx("10%", 800, 400, "huge", "am"),
        "shake", "תקציב טוקנים: עשרה אחוז")

    add("s18", 51.2, 54.4,
        desk() + win(300, 260, 1320, 560, "prompt", f'''
          <div style="font-size:29px;color:#3d4453;text-decoration:line-through">
            Could you please carefully refactor the following</div>
          <div style="font-size:29px;color:#3d4453;text-decoration:line-through">
            module, keeping the existing behaviour intact, and</div>
          <div style="font-size:29px;color:#3d4453;text-decoration:line-through">
            explain your reasoning step by step?</div>
          <div style="margin-top:44px;font-size:62px;color:{CYAN};font-weight:700">
            fix<span style="opacity:.85">▌</span></div>''', accent=AMBER),
        "push_in", "מוחק את ההסבר, נשאר fix")

    add("s19", 54.4, 57.6,
        desk() + f'''<div style="position:absolute;left:210px;top:250px;width:1500px;
          background:#12141c;border:1px solid {LINE};border-radius:14px;z-index:22;
          box-shadow:0 40px 120px rgba(0,0,0,.75);overflow:hidden">
          <div style="display:flex;height:64px;border-bottom:1px solid {LINE}">
            <div style="flex:1;border-right:1px solid {LINE};background:#1a1d28;
              display:flex;align-items:center;padding:0 20px;font-size:21px;color:{TXT}">docs</div>
            <div style="flex:1;border-right:1px solid {LINE};display:flex;align-items:center;
              padding:0 20px;font-size:21px;color:{DIM}">api</div>
            <div style="flex:1;display:flex;align-items:center;padding:0 20px;
              font-size:21px;color:{DIM}">issue</div>
            <div style="flex:3;display:flex;align-items:center;justify-content:center;
              font-size:21px;color:#2c3242">— 6 tabs closed —</div></div>
          <div style="height:430px;background:#0b0e15"></div></div>'''
        + gfx("9 → 3", 760, 760, "big", "am"),
        "ken_left", "סוגר טאבים")

    add("s20", 57.6, 60.8,
        desk() + person("panic", "warm", 640, 100, 660)
        + f'''<div style="position:absolute;left:580px;bottom:120px;z-index:30">
          {meter(7, RED, 760)}</div>''',
        "shake", "פאניקה + מד טוקנים מתרוקן")

    # ── שורת המם + ירידת ביט ────────────────────────────────────────────────
    add("s21", 60.8, 64.0,
        f'''<div style="position:absolute;inset:0;background:
          radial-gradient(1000px 700px at 50% 50%, rgba(77,232,255,.12), transparent 70%)"></div>
        <div style="position:absolute;left:110px;top:400px;width:1700px;z-index:30;
          font-size:68px;font-weight:800;line-height:1.42;letter-spacing:.005em;
          white-space:nowrap;color:#eafcff;text-shadow:0 0 30px rgba(77,232,255,.5)">
          You can charge a phone.<br>
          <span style="color:{RED};text-shadow:0 0 30px rgba(255,77,109,.55)">You can't
            charge a context window.</span></div>''',
        "hold", "שורת המם")

    add("s22", 64.0, 65.6,
        f'''<div style="position:absolute;inset:0;background:#040407"></div>
        <div style="position:absolute;left:930px;top:520px;width:22px;height:52px;
          background:{CYAN};opacity:.85;z-index:30;box-shadow:0 0 30px {CYAN}"></div>''',
        "hold", "דממה מוחלטת")

    # ── פזמון שיא — חיתוכים מהירים ──────────────────────────────────────────
    add("s23", 65.6, 67.2, desk() + person("shout", "both", 620, 90, 700), "punch", "בצעקה")
    add("s24", 67.2, 68.8,
        f'''<div style="position:absolute;inset:0;background:
          radial-gradient(760px 620px at 50% 48%, rgba(70,229,138,.16), transparent 66%)"></div>
        <div style="position:absolute;left:835px;top:290px;z-index:20">{battery(10, GREEN)}</div>'''
        + gfx("10%", 800, 470, "huge", "gr"), "punch", "עשרה אחוז סוללה")
    add("s25", 68.8, 70.4, desk() + person("shout", "warm", 620, 90, 700), "punch", "בצעקה")
    add("s26", 70.4, 72.0,
        f'''<div style="position:absolute;inset:0;background:
          radial-gradient(760px 620px at 50% 48%, rgba(255,77,109,.18), transparent 66%)"></div>
        <div style="position:absolute;left:580px;top:320px;z-index:20">{meter(10, RED, 760)}</div>'''
        + gfx("10%", 800, 470, "huge", "rd"), "punch", "עשרה אחוז טוקנים")

    add("s27", 72.0, 75.2,
        desk() + phone(745, 130, f'''<div style="font-size:120px;color:#39404f">0%</div>
          <div style="font-size:28px;color:#2f3542;letter-spacing:.2em">PHONE OFF</div>''',
          rot=13)
        + f'''<div style="position:absolute;right:150px;bottom:170px;font-size:34px;
          color:{DIM};z-index:30">// don't care</div>''',
        "ken_down", "הטלפון מת לו ביד, לא אכפת")

    add("s28", 75.2, 76.8, desk() + person("shout", "both", 600, 70, 740), "shake", "בצעקה, רחב")
    add("s29", 76.8, 78.4,
        f'''<div style="position:absolute;inset:0;background:
          radial-gradient(820px 620px at 50% 50%, rgba(255,77,109,.2), transparent 66%)"></div>
        <div style="position:absolute;left:580px;top:490px;z-index:22">{meter(4, RED, 760)}</div>'''
        + gfx("TOKENS", 700, 300, "mid", "rd"), "punch", "המד כמעט ריק")

    # ── סיום ────────────────────────────────────────────────────────────────
    add("s30", 78.4, 81.6,
        f'''<div style="position:absolute;inset:0;background:
          radial-gradient(900px 720px at 50% 50%, rgba(255,77,109,.24), transparent 68%)"></div>
        <div style="position:absolute;left:580px;top:660px;z-index:22">{meter(1, RED, 760)}</div>'''
        + gfx("1%", 830, 330, "huge", "rd"),
        "shake", "אחוז אחד")

    add("s31", 81.6, 83.2,
        desk() + win(300, 330, 1320, 420, "prompt", f'''
          <div style="font-size:60px;color:{CYAN};font-weight:700">
            fix bug pls<span style="opacity:.9">▌</span></div>
          <div style="margin-top:52px;font-size:26px;color:{DIM}">press ⏎ to send</div>''',
          accent=CYAN),
        "punch", "הפרומפט האחרון")

    add("s32", 83.2, 84.8,
        desk() + win(300, 330, 1320, 420, "claude-agent", f'''
          <div style="font-size:38px;color:{DIM}">thinking</div>
          <div style="margin-top:40px;display:flex;gap:20px">
            <span style="width:26px;height:26px;border-radius:50%;background:{CYAN}"></span>
            <span style="width:26px;height:26px;border-radius:50%;background:#2a3040"></span>
            <span style="width:26px;height:26px;border-radius:50%;background:#2a3040"></span>
          </div>''', accent=DIM),
        "hold", "דממה דרמטית — הסוכן חושב")

    add("s33", 84.8, 86.8,
        f'''<div style="position:absolute;inset:0;background:
          radial-gradient(900px 720px at 50% 50%, rgba(70,229,138,.2), transparent 68%)"></div>'''
        + desk() + person("joy", "cool", 620, 120, 680)
        + gfx("BUG FIXED", 610, 80, "mid", "gr"),
        "punch", "זה עבד — חגיגה")

    add("s34", 86.8, 87.4,
        f'''<div style="position:absolute;inset:0;background:#040407"></div>'''
        + gfx("0% TOKENS", 470, 460, "big", "rd"),
        "hold", "אפס אחוז טוקנים")

    add("s35", 87.4, 89.6,
        f'''<div style="position:absolute;inset:0;background:#06060a"></div>'''
        + desk() + person("calm", "cool", 660, 200, 620)
        + phone(1420, 330, f'''<div style="font-size:96px;font-weight:800;color:{GREEN}">90%</div>
          <div style="font-size:26px;color:{DIM};letter-spacing:.18em">BATTERY</div>''',
          rot=-7, scale=0.62),
        "ken_up", "הפאנץ' האחרון — הטלפון על תשעים")

    return S


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--force", action="store_true")
    p.add_argument("--only", nargs="*")
    a = p.parse_args()

    os.makedirs(HTML_DIR, exist_ok=True)
    os.makedirs(PNG_DIR, exist_ok=True)
    S = shots()

    total = sum(s["end"] - s["start"] for s in S)
    print(f"{len(S)} שוטים, {total:.2f} שניות סה\"כ")
    gaps = [(S[i]["end"], S[i + 1]["start"]) for i in range(len(S) - 1)
            if abs(S[i]["end"] - S[i + 1]["start"]) > 1e-6]
    if gaps:
        raise SystemExit(f"⛔ פערים/חפיפות בציר הזמן: {gaps}")

    json.dump([{k: v for k, v in s.items() if k != "html"} for s in S],
              open("assets/shots/shotlist.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    made = 0
    for s in S:
        if a.only and s["id"] not in a.only:
            continue
        h = os.path.join(HTML_DIR, f"{s['id']}.html")
        png = os.path.join(PNG_DIR, f"{s['id']}.png")
        open(h, "w", encoding="utf-8").write(s["html"])
        if not a.force and os.path.exists(png) and os.path.getsize(png) > 20000:
            continue
        r = subprocess.run(["node", "tools/shot.js", h, png, "1920", "1080"],
                           capture_output=True, text=True)
        if r.returncode != 0 or not os.path.exists(png):
            raise SystemExit(f"⛔ {s['id']} נכשל: {r.stderr[:300]}")
        made += 1
        print(f"  ✅ {s['id']}  {s['start']:5.1f}-{s['end']:5.1f}  {s['move']:11s} {s['note']}")
    print(f"צולמו {made} שוטים חדשים.")


if __name__ == "__main__":
    main()
