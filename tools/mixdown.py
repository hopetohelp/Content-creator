#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
mixdown.py — מיקס ומאסטר: לוקח סטמים ומוציא מאסטר מוכן, ביעד עוצמה מדויק.

🔴 למה הכלי הזה קיים: המדידה הראתה שגם אחרי שדרוג הסינתזה, המיקס הגולמי
היה 53% סאב ו-1% נוכחות. **זו לא בעיית סינתזה — זו בעיית מיקס.** כלים
שמנגנים יפה לחוד נשמעים בוציים ביחד אם אף אחד לא מפנה מקום לשני.

מה הוא עושה, לפי הסדר:
  1. **לכל סטם לפי תפקידו** — מסנן גבוה שמפנה את התחתית, לימיטציה לפס שלו,
     פאנינג ורוחב. זה הצעד שמנקה את הבוץ.
  2. **שליחה לריוורב** — הרמוניה ולידים מקבלים מרחב. בלי מרחב הכול נשמע
     כמו דמו MIDI.
  3. **אפיק ראשי** — רוויה מקבילה, דחיסת דבק, מדף אוויר ומעורר נוכחות.
  4. **יעד עוצמה אוטומטי** — מודד ב-BS.1770 ומכוונן עד שהוא בטווח,
     עם מרווח ל-True Peak. מחליף את הניחוש הידני.

שימוש:
  python3 tools/mixdown.py --out mix.wav --target house \\
     drums=beat.wav bass=bass.wav harmony=pad.wav lead=stab.wav

  # יחס עוצמה ידני לסטם: role=file:gain_db
  python3 tools/mixdown.py --out mix.wav --target rap \\
     drums=beat.wav:0 harmony=pad.wav:-4 vox=vox.wav:+1
"""
import argparse, os, sys
import numpy as np, soundfile as sf

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import synth as S
import loudness as LD

SR = S.SR

# לכל תפקיד: מסנן-גבוה, מסנן-נמוך, עוצמה, רוחב, שליחה לריוורב, הגברת נוכחות.
# 🔑 מסנן-הגבוה על ההרמוניה הוא הצעד היחיד שהכי משנה את בהירות המיקס:
#    הוא מפנה את כל התחתית לקיק ולבאס בלבד.
ROLES = {
    "drums":   dict(hp=28,   lp=None, gain=0.0,  width=0.15, verb=0.05, pres=0.30),
    "bass":    dict(hp=25,   lp=170,  gain=-1.0, width=0.00, verb=0.00, pres=0.00),
    "harmony": dict(hp=190,  lp=None, gain=-5.0, width=0.45, verb=0.30, pres=0.15),
    "lead":    dict(hp=240,  lp=None, gain=-6.0, width=0.35, verb=0.24, pres=0.35),
    "vox":     dict(hp=95,   lp=None, gain=-1.5, width=0.05, verb=0.12, pres=0.45),
    "fx":      dict(hp=300,  lp=None, gain=-9.0, width=0.60, verb=0.40, pres=0.20),
}

TARGETS = LD.TARGETS

# כל סטם מיושר לעוצמה הזאת לפני שמופעל עליו יחס העוצמה של תפקידו.
# כך היחסים ב-ROLES אומרים משהו אמיתי, בלי קשר למקור הסטם.
STEM_REF_LUFS = -20.0

# מבנה: לכל מקטע, עוצמה יחסית לכל תפקיד + פתיחת מסנן על ההרמוניה.
# 🔴 למה זה קיים: במדידה מול רפרנס אמיתי, לולאה זהה החוזרת על עצמה נתנה
# סטיית תקן 0.31dB בגורם השיא מול 2.89 ברפרנס — כלומר "שטוח לגמרי".
# הבדל בין דמו להפקה הוא שאלמנטים נכנסים ויוצאים, לא שהם מנוגנים טוב יותר.
SECTIONS = {
    #            drums bass harmony lead  vox   fx   פתיחת מסנן (יחס מ-fc)
    "intro":  dict(drums=0.55, bass=0.70, harmony=0.30, lead=0.00, vox=0.0, fx=0.5, open=0.35),
    "build":  dict(drums=0.85, bass=0.85, harmony=0.65, lead=0.35, vox=0.6, fx=0.9, open=(0.35, 1.0)),
    "drop":   dict(drums=1.00, bass=1.00, harmony=1.00, lead=1.00, vox=1.0, fx=0.6, open=1.0),
    "break":  dict(drums=0.15, bass=0.30, harmony=1.00, lead=0.55, vox=0.9, fx=1.0, open=0.75),
    "outro":  dict(drums=0.65, bass=0.45, harmony=0.60, lead=0.20, vox=0.4, fx=0.7, open=0.5),
}


def _section_env(n, bpm, sections, role, bars=8, sr=SR):
    """מעטפת עוצמה לתפקיד אחד לאורך כל השיר, לפי רשימת המקטעים."""
    seg = int(bars * 4 * 60.0 / bpm * sr)
    env = np.zeros(n)
    for i in range(int(np.ceil(n / seg)) if seg else 1):
        name = sections[i % len(sections)]
        v = SECTIONS[name].get(role, 1.0)
        a, b = i * seg, min(n, (i + 1) * seg)
        if b <= a:
            break
        env[a:b] = np.linspace(*v, b - a) if isinstance(v, tuple) else v
    # החלקה של 60ms — מונעת קליקים בתפרים
    k = max(1, int(0.06 * sr)); w = np.hanning(k * 2 + 1); w /= w.sum()
    return np.convolve(env, w, mode="same")


# ── דבק האפיק: pedalboard אם קיים, אחרת numpy ──────────────────────────────
try:
    import pedalboard as _pb
    HAVE_PB = True
except ImportError:                       # הכלי חייב לעבוד גם בלי התלות
    HAVE_PB = False


def _bus_glue(bus, sr=SR):
    """דחיסת דבק + מדף אוויר על האפיק הראשי.

    משתמש ב-pedalboard (מנוע JUCE, C++) כשהוא מותקן — איכות אולפן ופי ~7
    מהר יותר. נופל בחזרה למימוש ה-numpy כשאינו מותקן, כך שהכלי לא נשבר.

    🔴 **הלימיטר של pedalboard לא משמש כאן בכוונה.** נמדד: `Limiter`
    מחזיר 0.00 dBFS בכל סף שנותנים לו — הוא מנרמל את הפלט בחזרה לשיא מלא,
    בדיוק כמו `alimiter` של ffmpeg. הוא **לא** לימיטר-תקרה. שער ה-True Peak
    נשאר על `synth.limit(true_peak=True)`, שנמדד ומחזיק את התקרה בפועל."""
    if not HAVE_PB:
        bus = S.compress(bus, thresh_db=-11.0, ratio=1.7)
        return _fft_eq(bus, air_db=3.2, air_hz=9000.0, hp=22)
    board = _pb.Pedalboard([
        _pb.HighpassFilter(22),
        _pb.Compressor(threshold_db=-11.0, ratio=1.7, attack_ms=12, release_ms=140),
        _pb.HighShelfFilter(cutoff_frequency_hz=9000, gain_db=3.2),
    ])
    return np.asarray(board(bus.astype(np.float32).T, sr), dtype=float).T


# ── EQ בתחום התדר ───────────────────────────────────────────────────────────
def _fft_eq(x, sr=SR, hp=None, lp=None, air_db=0.0, air_hz=8000.0,
            mud_db=0.0, mud_hz=320.0):
    """מסננים ומדפים בתחום התדר. מדויק, ובלי לולאות רקורסיביות איטיות."""
    n = len(x)
    X = np.fft.rfft(x, axis=0)
    f = np.fft.rfftfreq(n, 1 / sr)[:, None] if x.ndim == 2 else np.fft.rfftfreq(n, 1 / sr)
    H = np.ones_like(f)
    if hp:                                   # מעביר-גבוה מסדר 2, שיפוע רך
        H = H * (f ** 2 / (f ** 2 + hp ** 2))
    if lp:                                   # מסדר 4 — מסדר 2 לא הספיק במדידה
        H = H * (lp ** 2 / (f ** 2 + lp ** 2)) ** 2
    if air_db:                               # מדף גבוה
        H = H * (1.0 + (10 ** (air_db / 20.0) - 1.0) / (1.0 + (air_hz / np.maximum(f, 1e-9)) ** 2))
    if mud_db:                               # פעמון רחב לניקוי הנמוך-אמצע
        q = 1.1
        H = H * (1.0 + (10 ** (mud_db / 20.0) - 1.0)
                 * np.exp(-(np.log2(np.maximum(f, 1e-9) / mud_hz) ** 2) / (2 * q ** 2)))
    return np.fft.irfft(X * H, n=n, axis=0)


def load_stem(path):
    y, sr = sf.read(path, always_2d=True)
    if sr != SR:
        raise SystemExit(f"⛔ {path} בקצב {sr} במקום {SR}. להמיר: ffmpeg -i in -ar {SR} out")
    if y.shape[1] == 1:
        y = np.repeat(y, 2, axis=1)
    return y.astype(float)


def mixdown(stems, target="house", verb_seconds=1.6, verb_decay=5.0, seed=5,
            headroom_db=1.6, sections=None, bpm=126.0, bars=8):
    """stems: רשימת (role, path, gain_db). מחזיר (מאסטר, דוח)."""
    n = max(len(load_stem(p)) for _, p, _ in stems)
    bus = np.zeros((n, 2))
    send = np.zeros((n, 2))                       # אפיק שליחה לריוורב

    for role, path, gdb in stems:
        if role not in ROLES:
            raise SystemExit(f"⛔ תפקיד לא מוכר: '{role}'. מותר: {', '.join(ROLES)}")
        R = ROLES[role]
        y = load_stem(path)
        y = np.pad(y, ((0, n - len(y)), (0, 0))) if len(y) < n else y[:n]
        # 0. יישור עוצמה לפני הכול ("gain staging").
        # 🔴 בלי זה הכלי עובד רק על סטמים מהכלים שלנו, שכולם מנורמלים לשיא
        # דומה. סטם מיובא (סאונדפונט, דגימה, הקלטה) דינמי הרבה יותר, ה-RMS
        # שלו נמוך — והוא פשוט נעלם. נמדד: הרמוניה מיובאת ירדה ל-2% מהאנרגיה.
        st_l = LD.integrated_lufs(
            [LD.k_weight(np.ascontiguousarray(y[:, c]), SR) for c in range(2)], SR)
        if np.isfinite(st_l):
            y = y * 10 ** ((STEM_REF_LUFS - st_l) / 20.0)
        # 1. פינוי מקום: מסנן גבוה לפי התפקיד + ניקוי הנמוך-אמצע
        y = _fft_eq(y, hp=R["hp"], lp=R["lp"],
                    mud_db=(-3.5 if role in ("harmony", "lead", "fx") else 0.0))
        # 2. נוכחות: מעורר גבהים רק במידה שהתפקיד דורש
        if R["pres"]:
            y = np.stack([S.exciter(y[:, c], amount=R["pres"]) for c in range(2)], axis=1)
        # 3. רוחב ועוצמה
        if R["width"]:
            y = S.widen(y, R["width"])
        y = y * 10 ** ((R["gain"] + gdb) / 20.0)
        # מבנה: אלמנטים נכנסים ויוצאים לאורך השיר
        if sections:
            y = y * _section_env(n, bpm, sections, role, bars)[:, None]
        bus += y
        if R["verb"]:
            send += y * R["verb"]

    # 4. מרחב
    if np.any(send):
        ir = S.reverb_ir(verb_seconds, verb_decay, sr=SR, seed=seed)
        wet = S.convolve(send, ir)
        wet = _fft_eq(wet, hp=320)                # ריוורב בלי תחתית = מרחב בלי בוץ
        bus += wet * 0.33

    # 5. אפיק ראשי — רוויה מקבילה, דבק, אוויר
    bus = S.saturate(bus, 1.5, mix=0.32)
    bus = _bus_glue(bus)
    bus = S.widen(bus, 0.12)

    # 6. יעד עוצמה — מכוונן עד שהוא בטווח, במקום לנחש
    lo, hi = TARGETS[target]["lufs"]
    tp_max = TARGETS[target]["tp"] - headroom_db      # מרווח למקודד AAC
    aim = (lo + hi) / 2.0
    ceiling = 10 ** (tp_max / 20.0)

    def _lufs(sig):
        return LD.integrated_lufs(
            [LD.k_weight(np.ascontiguousarray(sig[:, c]), SR) for c in range(2)], SR)

    # ⚠️ הנרמול קורה פעם אחת, מחוץ ללולאה. אם הוא בתוכה הוא מבטל בכל סיבוב
    # בדיוק את תיקון העוצמה שזה עתה הוחל — והלולאה לא מתכנסת לעולם.
    # והמדידה היא תמיד על המועמד **אחרי** הלימיטר, כי הוא זה שמשנה את העוצמה.
    # ההתכנסות רצה עם לימיטר-דגימה (זול), ורק אחריה מופעל לימיטר ה-True Peak
    # (יקר — דגימת-יתר ×4). כך הפעולה היקרה רצה פעמיים במקום שמונה.
    work = S.norm(bus, 0.98)
    out = S.limit(work, ceiling)
    lufs = _lufs(out)
    for _ in range(8):
        if not np.isfinite(lufs) or lo <= lufs <= hi:
            break
        work = work * 10 ** ((aim - lufs) / 20.0)
        out = S.limit(work, ceiling)
        lufs = _lufs(out)
    out = S.limit(out, ceiling, true_peak=True)
    lufs = _lufs(out)
    if np.isfinite(lufs) and not (lo <= lufs <= hi):     # תיקון אחרון אם סטה
        out = S.limit(out * 10 ** ((aim - lufs) / 20.0), ceiling, true_peak=True)
        lufs = _lufs(out)
    tp = LD.true_peak_dbtp([out[:, 0], out[:, 1]], SR)
    rep = dict(lufs=lufs, tp=tp, target=target, range=(lo, hi))
    return out.astype(np.float32), rep


def parse_stem(arg):
    """role=path[:gain_db]"""
    if "=" not in arg:
        raise SystemExit(f"⛔ '{arg}' — הפורמט הוא role=file.wav או role=file.wav:-3")
    role, rest = arg.split("=", 1)
    gain = 0.0
    if ":" in rest and not os.path.exists(rest):
        rest, g = rest.rsplit(":", 1)
        gain = float(g)
    if not os.path.exists(rest):
        raise SystemExit(f"⛔ הקובץ לא נמצא: {rest}")
    return role.strip(), rest, gain


def main():
    p = argparse.ArgumentParser(description="מיקס ומאסטר לסטמים")
    p.add_argument("stems", nargs="+", help="role=file.wav[:gain_db]")
    p.add_argument("--out", required=True)
    p.add_argument("--target", default="house", choices=list(TARGETS))
    p.add_argument("--headroom", type=float, default=1.6,
                   help="מרווח True Peak מתחת ליעד, ל-AAC (ברירת מחדל 1.6dB)")
    p.add_argument("--verb", type=float, default=1.6, help="אורך הריוורב בשניות")
    p.add_argument("--seed", type=int, default=5)
    p.add_argument("--arrange", help="מקטעים מופרדים בפסיק: intro,build,drop,break,drop")
    p.add_argument("--bpm", type=float, default=126.0, help="נדרש עם --arrange")
    p.add_argument("--bars", type=int, default=8, help="תיבות לכל מקטע")
    a = p.parse_args()

    stems = [parse_stem(s) for s in a.stems]
    secs = None
    if a.arrange:
        secs = [x.strip() for x in a.arrange.split(",")]
        bad = [x for x in secs if x not in SECTIONS]
        if bad:
            raise SystemExit(f"⛔ מקטע לא מוכר: {bad}. מותר: {', '.join(SECTIONS)}")
    y, rep = mixdown(stems, a.target, a.verb, seed=a.seed, headroom_db=a.headroom,
                     sections=secs, bpm=a.bpm, bars=a.bars)
    sf.write(a.out, y, SR, subtype="PCM_16")
    lo, hi = rep["range"]
    ok = lo <= rep["lufs"] <= hi and rep["tp"] < TARGETS[a.target]["tp"]
    print(f"נכתב: {a.out}  ({len(stems)} סטמים, יעד '{a.target}'"
          + (f", מבנה: {'→'.join(secs)}" if secs else "") + ")")
    print(f"   LUFS {rep['lufs']:.2f}  (יעד {lo} עד {hi})   "
          f"True Peak {rep['tp']:.2f} dBTP")
    print("   ✅ בתוך היעד" if ok else "   ⚠️ מחוץ ליעד — לבדוק את איזוני הסטמים")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
