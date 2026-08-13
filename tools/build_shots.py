#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_shots.py — מגדיר את רשימת השוטים, כותב HTML, ומצלם ל-PNG.

מקור האמת לרשימת השוטים. כל שוט מתחיל ומסתיים על **גבול תיבה** (1.6 שניות
ב-150 BPM), כי החיתוכים חייבים ליפול על הדופק ולא בין דופקים.

**60% מהשוטים אינם מראים פנים** — מסכים, אובייקטים, ידיים ומדים. זה מוריד
את סיכון העקביות של הדמות ונראה יותר קולנועי (מסמך 2, סעיף 5).

🔴 **חלוקת העבודה בין תצלום ל-HTML:**
  • **בן אדם, חדר, אובייקט** ⇒ תצלום ריאליסטי מ-`fetch_image.py`.
  • **כל דבר שיש בו טקסט או מספר** ⇒ HTML מולבש מעל התצלום.
מודל תמונה מחזיר טרמינל עם ג׳יבריש, וכאן **המספרים הם הבדיחה** — `10%`
חייב להיות מדויק.

שימוש:
    python3 tools/build_shots.py                # בונה ומצלם את מה שחסר
    python3 tools/build_shots.py --force        # מצלם הכול מחדש
    python3 tools/build_shots.py --only s07 s12
"""
import argparse, json, os, subprocess, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from character import svg as char                                   # noqa: E402
from shot_kit import (AMBER, CYAN, DIM, GREEN, LINE, RED, TXT,      # noqa: E402
                      battery, gfx, grade, meter, page, phone, photo, win)

HTML_DIR = "assets/shots/html"
PNG_DIR = "assets/shots"


def person(name, darken=0.06, scale=1.0):
    """שוט דמות = תצלום מלא-פריים. `character.py` נשאר בריפו כגיבוי בלבד."""
    return photo(f"assets/stills/char_{name}.jpg", darken=darken, scale=scale, z=1)


def code_lines(rows):
    out = []
    for n, (cls, txt) in enumerate(rows, 1):
        out.append(f'<div><span class="c-dim" style="display:inline-block;width:56px;'
                   f'text-align:right;margin-right:26px">{n}</span>'
                   f'<span class="{cls}">{txt}</span></div>')
    return "".join(out)


def desk(plate="room_wide", darken=0.52, blur=4):
    """רקע החדר כתצלום. מוכהה ומטושטש כדי שממשק שמונח מעליו יישאר קריא."""
    return photo(f"assets/stills/{plate}.jpg", darken=darken, blur=blur, z=1)


# ─────────────────────────────────────────────────────────────────────────────
# רשימת השוטים. start/end על גבולות תיבה של 1.6 שניות.
# move = תנועת ffmpeg שתופעל בשלב הרינדור.
# ─────────────────────────────────────────────────────────────────────────────
def shots():
    S = []
    def add(sid, start, end, body, move, note):
        S.append(dict(id=sid, start=start, end=end, html=page(body) , move=move, note=note))

    # ── פתיחה קרה ───────────────────────────────────────────────────────────
    add("s01", 0.0, 3.2,
        photo("assets/stills/phone_hand.jpg", darken=0.30, z=1) + grade()
        + phone(1210, 130, f'''{battery(10, RED)}
          <div style="font-size:86px;font-weight:800;color:{RED}">10%</div>
          <div style="font-size:30px;color:{DIM};letter-spacing:.16em">BATTERY</div>''',
          rot=-4, scale=0.86)
        + gfx("10% BATTERY", 150, 726, "mid", "rd"),
        "push_in", "טלפון: עשרה אחוז סוללה")

    add("s02", 3.2, 6.4,
        desk("monitor_back", darken=0.55, blur=5) + grade()
        + win(300, 190, 1320, 700, "claude-agent — session", f'''
          {code_lines([("c-dim","$ agent run --task refactor"),
                       ("c-gr","✓ 41 files analyzed"),
                       ("c-gr","✓ patch applied"),
                       ("c-dim","  streaming response…")])}
          <div style="margin-top:44px;color:{DIM};font-size:23px;letter-spacing:.1em">TOKEN BUDGET</div>
          <div style="margin-top:14px">{meter(10, RED, 1180)}</div>
          <div style="margin-top:20px;font-size:70px;font-weight:800;color:{RED}">10% remaining</div>''',
          accent=RED)
        + gfx("10% TOKENS", 560, 748, "mid", "rd"),
        "push_in", "מסך: עשרה אחוז טוקנים")

    add("s03", 6.4, 8.0, person("dread") + grade(), "snap_in", "קלוז-אפ: אוי לא")

    add("s04", 8.0, 9.6,
        person("shout", darken=0.20) + grade(0.22, 0.14)
        + gfx("TEN PERCENT", 415, 110, "big", "cy"),
        "shake", "כניסת הביט — כרטיס פתיחה")

    # ── בית 1: סוללה ────────────────────────────────────────────────────────
    add("s05", 9.6, 12.8,
        photo("assets/stills/phone_hand.jpg", darken=0.28, z=1) + grade()
        + phone(1180, 150, f'''{battery(10, RED)}
          <div style="font-size:72px;font-weight:800;color:{RED}">10%</div>
          <div style="width:300px;margin-top:10px">{meter(10, RED, 300)}</div>''',
          rot=-4, scale=0.86),
        "ken_left", "פס אדום בפינה")

    add("s06", 12.8, 16.0,
        desk("desk_plate", darken=0.5, blur=5) + grade()
        + f'''<div style="position:absolute;left:430px;top:330px;width:1060px;
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
        photo("assets/stills/cable_floor.jpg", darken=0.18, z=1) + grade(),
        "ken_right", "כבל זרוק על הרצפה")

    add("s08", 19.2, 22.4,
        photo("assets/stills/powerbank.jpg", darken=0.18, z=1) + grade()
        + gfx("2021", 1480, 880, "mid", "am"),
        "ken_up", "מטען נייד ישן")

    add("s09", 22.4, 25.6,
        desk("desk_plate", darken=0.5, blur=5) + grade()
        + win(430, 250, 1060, 560, "settings — battery", f'''
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
        photo("assets/stills/keyboard.jpg", darken=0.55, z=1) + grade()
        + f'''<div style="position:absolute;left:460px;top:400px;width:1000px;z-index:24">
          <div style="font-size:30px;color:{DIM};letter-spacing:.2em;margin-bottom:26px">BRIGHTNESS</div>
          {meter(6, "#8a93a6", 1000)}
          <div style="margin-top:30px;font-size:26px;color:#5b6474">nearly dark — still fine</div></div>''',
        "ken_down", "בהירות מונמכת")

    add("s11", 28.8, 32.0,
        person("work", darken=0.12) + grade()
        + f'''<div style="position:absolute;right:110px;bottom:130px;font-size:32px;
          color:#8892a5;z-index:30">// still working</div>''',
        "ken_left", "הוא ממשיך לעבוד, אדיש")

    # ── הוק קצר ─────────────────────────────────────────────────────────────
    add("s12", 32.0, 35.2,
        photo("assets/stills/room_wide.jpg", darken=0.62, blur=6, z=1)
        + f'''<div style="position:absolute;inset:0;z-index:2;background:
          radial-gradient(760px 620px at 50% 46%, rgba(70,229,138,.20), transparent 66%)"></div>
        <div style="position:absolute;left:835px;top:250px;z-index:20">{battery(10, GREEN)}</div>'''
        + gfx("10%", 800, 430, "huge", "gr")
        + gfx("BATTERY", 700, 720, "mid", "gr"),
        "punch", "עשרה אחוז סוללה — אני אשרוד")

    add("s13", 35.2, 38.4,
        photo("assets/stills/monitor_back.jpg", darken=0.62, blur=6, z=1)
        + f'''<div style="position:absolute;inset:0;z-index:2;background:
          radial-gradient(760px 620px at 50% 46%, rgba(255,77,109,.22), transparent 66%)"></div>
        <div style="position:absolute;left:580px;top:270px;z-index:20">{meter(10, RED, 760)}</div>'''
        + gfx("10%", 800, 430, "huge", "rd")
        + gfx("TOKENS", 740, 720, "mid", "rd"),
        "punch", "עשרה אחוז טוקנים — בקושי חי")

    # ── בית 2: טוקנים ───────────────────────────────────────────────────────
    add("s14", 38.4, 41.6,
        desk("monitor_back", darken=0.55, blur=5) + grade()
        + win(210, 170, 1500, 740, "main.py — agent session", code_lines([
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
        desk("desk_plate", darken=0.55, blur=5) + grade()
        + win(260, 200, 1400, 680, "pytest", code_lines([
            ("c-gr", "tests/test_core.py .......... [ 34%]"),
            ("c-gr", "tests/test_api.py  .......... [ 68%]"),
            ("c-gr", "tests/test_cli.py  .......... [100%]"),
            ("c-dim", ""),
            ("c-gr b", "==== 96 passed in 4.21s ===="),
        ]), accent=GREEN),
        "ken_right", "כל הבדיקות ירוקות")

    add("s16", 44.8, 48.0,
        desk("monitor_back", darken=0.58, blur=5) + grade()
        + win(210, 170, 1500, 740, "main.py — agent session", code_lines([
            ("c-gr", "    for f in files:"),
            ("c-gr", "        f.rewrite(plan[f])"),
            ("c-gr", "    return commit(files)"),
            ("c-dim", ""),
            ("c-gr", "▸ agent: 41/41 files done"),
            ("c-gr", "▸ tests: 96 passed"),
            ("c-dim", "▸ writing summary…"),
        ])) + f'''<div style="position:absolute;left:1250px;top:790px;font-size:31px;
          color:#7f8a9e;z-index:40">tokens 10%</div>
        <div style="position:absolute;left:1216px;top:774px;width:266px;height:66px;
          border:2px solid {AMBER};border-radius:10px;z-index:39;opacity:.75;
          box-shadow:0 0 40px rgba(255,179,71,.28)"></div>''',
        "zoom_corner", "מספר אפור קטן בפינה")

    add("s17", 48.0, 51.2,
        photo("assets/stills/monitor_back.jpg", darken=0.60, blur=5, z=1)
        + f'''<div style="position:absolute;inset:0;z-index:2;background:
          radial-gradient(900px 700px at 50% 50%, rgba(255,179,71,.24), transparent 68%)"></div>
        <div style="position:absolute;left:580px;top:600px;z-index:22">{meter(10, AMBER, 760)}</div>'''
        + gfx("TOKEN BUDGET", 555, 300, "mid", "am")
        + gfx("10%", 800, 400, "huge", "am"),
        "shake", "תקציב טוקנים: עשרה אחוז")

    add("s18", 51.2, 54.4,
        desk("desk_plate", darken=0.55, blur=5) + grade()
        + win(300, 260, 1320, 560, "prompt", f'''
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
        desk("monitor_back", darken=0.55, blur=5) + grade()
        + f'''<div style="position:absolute;left:210px;top:250px;width:1500px;
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
        person("panic", darken=0.10) + grade(0.10, 0.24)
        + f'''<div style="position:absolute;left:580px;bottom:110px;z-index:30">
          {meter(7, RED, 760)}</div>''',
        "shake", "פאניקה + מד טוקנים מתרוקן")

    # ── שורת המם + ירידת ביט ────────────────────────────────────────────────
    add("s21", 60.8, 64.0,
        photo("assets/stills/room_wide.jpg", darken=0.70, blur=7, z=1)
        + f'''<div style="position:absolute;inset:0;z-index:2;background:
          radial-gradient(1000px 700px at 50% 50%, rgba(77,232,255,.14), transparent 70%)"></div>
        <div style="position:absolute;left:110px;top:400px;width:1700px;z-index:30;
          font-size:68px;font-weight:800;line-height:1.42;letter-spacing:.005em;
          white-space:nowrap;color:#eafcff;text-shadow:0 0 30px rgba(77,232,255,.5)">
          You can charge a phone.<br>
          <span style="color:{RED};text-shadow:0 0 30px rgba(255,77,109,.55)">You can't
            charge a context window.</span></div>''',
        "hold", "שורת המם")

    # תיבת הדממה. כהה מאוד — אבל **לא שחורה**: פריים שחור באמצע קליפ נקרא
    # אצל הצופה כתקלה, ו-QA מסמן אותו ככישלון.
    add("s22", 64.0, 65.6,
        photo("assets/stills/room_wide.jpg", darken=0.80, blur=3, z=1)
        + f'''<div style="position:absolute;left:948px;top:500px;width:20px;height:54px;
          background:{CYAN};opacity:.95;z-index:32;box-shadow:0 0 46px {CYAN}"></div>''',
        "hold", "דממה מוחלטת")

    # ── פזמון שיא — חיתוכים מהירים ──────────────────────────────────────────
    add("s23", 65.6, 67.2, person("shout", darken=0.10) + grade(0.20, 0.14), "punch", "בצעקה")
    add("s24", 67.2, 68.8,
        photo("assets/stills/room_wide.jpg", darken=0.62, blur=6, z=1)
        + f'''<div style="position:absolute;inset:0;z-index:2;background:
          radial-gradient(760px 620px at 50% 48%, rgba(70,229,138,.20), transparent 66%)"></div>
        <div style="position:absolute;left:835px;top:290px;z-index:20">{battery(10, GREEN)}</div>'''
        + gfx("10%", 800, 470, "huge", "gr"), "punch", "עשרה אחוז סוללה")
    add("s25", 68.8, 70.4, person("shout2", darken=0.10) + grade(0.12, 0.22), "punch", "בצעקה")
    add("s26", 70.4, 72.0,
        photo("assets/stills/monitor_back.jpg", darken=0.62, blur=6, z=1)
        + f'''<div style="position:absolute;inset:0;z-index:2;background:
          radial-gradient(760px 620px at 50% 48%, rgba(255,77,109,.22), transparent 66%)"></div>
        <div style="position:absolute;left:580px;top:320px;z-index:20">{meter(10, RED, 760)}</div>'''
        + gfx("10%", 800, 470, "huge", "rd"), "punch", "עשרה אחוז טוקנים")

    add("s27", 72.0, 75.2,
        photo("assets/stills/phone_desk.jpg", darken=0.30, z=1) + grade()
        + gfx("0%", 830, 300, "huge", "cy")
        + f'''<div style="position:absolute;right:140px;bottom:150px;font-size:34px;
          color:#8892a5;z-index:30">// don't care</div>''',
        "ken_down", "הטלפון מת לו ביד, לא אכפת")

    add("s28", 75.2, 76.8, person("shout", darken=0.14, scale=1.08) + grade(0.20, 0.16),
        "shake", "בצעקה, רחב")
    add("s29", 76.8, 78.4,
        photo("assets/stills/monitor_back.jpg", darken=0.62, blur=6, z=1)
        + f'''<div style="position:absolute;inset:0;z-index:2;background:
          radial-gradient(820px 620px at 50% 50%, rgba(255,77,109,.24), transparent 66%)"></div>
        <div style="position:absolute;left:580px;top:490px;z-index:22">{meter(4, RED, 760)}</div>'''
        + gfx("TOKENS", 700, 300, "mid", "rd"), "punch", "המד כמעט ריק")

    # ── סיום ────────────────────────────────────────────────────────────────
    add("s30", 78.4, 81.6,
        photo("assets/stills/room_wide.jpg", darken=0.66, blur=6, z=1)
        + f'''<div style="position:absolute;inset:0;z-index:2;background:
          radial-gradient(900px 720px at 50% 50%, rgba(255,77,109,.28), transparent 68%)"></div>
        <div style="position:absolute;left:580px;top:660px;z-index:22">{meter(1, RED, 760)}</div>'''
        + gfx("1%", 830, 330, "huge", "rd"),
        "shake", "אחוז אחד")

    add("s31", 81.6, 83.2,
        desk("desk_plate", darken=0.5, blur=5) + grade()
        + win(300, 330, 1320, 420, "prompt", f'''
          <div style="font-size:60px;color:{CYAN};font-weight:700">
            fix bug pls<span style="opacity:.9">▌</span></div>
          <div style="margin-top:52px;font-size:26px;color:{DIM}">press ⏎ to send</div>''',
          accent=CYAN),
        "punch", "הפרומפט האחרון")

    add("s32", 83.2, 84.8,
        desk("monitor_back", darken=0.58, blur=5) + grade()
        + win(300, 330, 1320, 420, "claude-agent", f'''
          <div style="font-size:38px;color:{DIM}">thinking</div>
          <div style="margin-top:40px;display:flex;gap:20px">
            <span style="width:26px;height:26px;border-radius:50%;background:{CYAN}"></span>
            <span style="width:26px;height:26px;border-radius:50%;background:#2a3040"></span>
            <span style="width:26px;height:26px;border-radius:50%;background:#2a3040"></span>
          </div>''', accent=DIM),
        "hold", "דממה דרמטית — הסוכן חושב")

    add("s33", 84.8, 86.8,
        person("joy", darken=0.10) + grade(0.20, 0.10)
        + gfx("BUG FIXED", 610, 80, "mid", "gr"),
        "punch", "זה עבד — חגיגה")

    add("s34", 86.8, 87.4,
        photo("assets/stills/monitor_back.jpg", darken=0.78, blur=4, z=1)
        + gfx("0% TOKENS", 470, 460, "big", "rd"),
        "hold", "אפס אחוז טוקנים")

    add("s35", 87.4, 89.6,
        person("calm", darken=0.14) + grade()
        + phone(1450, 360, f'''<div style="font-size:96px;font-weight:800;color:{GREEN}">90%</div>
          <div style="font-size:26px;color:{DIM};letter-spacing:.18em">BATTERY</div>''',
          rot=-7, scale=0.58),
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
