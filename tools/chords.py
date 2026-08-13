#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
chords.py — הרמוניה ומלודיה פרוצדורליות, מסונתזות מאפס ב-numpy.
אפס תלות במודלים, אפס רשת, אפס GPU, דטרמיניסטי (seed קבוע -> אותו קובץ בדיוק).

למה הכלי הזה קיים: `beat.py` נותן תופים ובאס בלבד. הפער תועד ב-
`מסמכים/מחקר/4. הנחיה — פופ.md` — "פופ בלי הרמוניה ובלי שירה הוא לא פופ".
זה הכלי שסוגר את הפער, ומשלים את `beat.py` לשיר.

תכולה:  אקורדים דיאטוניים מסולם, חמישה קולות (פד, פריטה, פעמון, סטאב, באס),
        מסנן מעביר-נמוך, וסייד-צ׳יין מובנה (הנשימה של האוס).

שימוש:
  python3 tools/chords.py --out pad.wav --seconds 30 --bpm 108 --key Am --prog "i VI III VII"
  python3 tools/chords.py --out stab.wav --bpm 126 --key Fm --voice stab --sidechain four
  python3 tools/chords.py --out bass.wav --bpm 140 --key Cm --voice bass --prog "i i VI VII"
"""
import argparse, os, sys
import numpy as np, soundfile as sf

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import synth as S

SR = S.SR

# ── תיאוריה ─────────────────────────────────────────────────────────────────
PC = {"C":0,"C#":1,"DB":1,"D":2,"D#":3,"EB":3,"E":4,"FB":4,"F":5,"E#":5,
      "F#":6,"GB":6,"G":7,"G#":8,"AB":8,"A":9,"A#":10,"BB":10,"B":11,"CB":11}
MAJOR = [0, 2, 4, 5, 7, 9, 11]
MINOR = [0, 2, 3, 5, 7, 8, 10]          # מינור טבעי
ROMAN = {"I":0,"II":1,"III":2,"IV":3,"V":4,"VI":5,"VII":6}


def parse_key(key):
    """'Am' -> (9, MINOR) · 'C' -> (0, MAJOR) · 'F#m' -> (6, MINOR)"""
    k = key.strip()
    minor = k.lower().endswith("m")
    if minor:
        k = k[:-1]
    k = k.upper()
    if k not in PC:
        raise SystemExit(f"⛔ סולם לא מוכר: '{key}'. דוגמאות: Am, C, F#m, Ebm")
    return PC[k], (MINOR if minor else MAJOR)


def chord_midi(numeral, root_pc, scale, octave=3):
    """מחזיר תווי MIDI של אקורד דיאטוני. ערימת שלישיות מתוך הסולם עצמו —
    כך האיכות (מז'ור/מינור/מוקטן) יוצאת נכונה מאליה ואי אפשר לטעות בה."""
    n = numeral.strip()
    seventh = n.endswith("7")
    if seventh:
        n = n[:-1]
    n = n.rstrip("°o")
    deg = ROMAN.get(n.upper())
    if deg is None:
        raise SystemExit(f"⛔ דרגה לא מוכרת: '{numeral}'. מותר: I..VII, עם 7 בסוף")
    steps = [0, 2, 4] + ([6] if seventh else [])
    out = []
    for s in steps:
        i = deg + s
        out.append(12 * (octave + 1) + root_pc + scale[i % 7] + 12 * (i // 7))
    return out


def hz(midi):
    return 440.0 * 2.0 ** ((midi - 69) / 12.0)


# ── סינתזה ──────────────────────────────────────────────────────────────────
# 🔴 כל קול מוגדר כאן כגל עשיר בהרמוניות + מסנן שנע בזמן + יוניסון סטריאו.
# הגרסה הקודמת השתמשה בסינוסים טהורים במונו — ובמדידה זה נתן 0.1% אנרגיה
# בפס הנוכחות ומתאם ערוצים 0.999. זו הסיבה שהיא נשמעה חיוורת וקטנה.
VOICES = {
    #            גל       מעטפת (a,d,s,r)            חיתוך התחלה/סוף   רזוננס יוניסון פריסה
    "pad":   dict(wave="saw",    env=(0.35, 0.45, 0.75, 0.60), fc=(700, 2600),  res=0.5, uni=5, spread=1.00, drive=1.3),
    "keys":  dict(wave="tri",    env=(0.004, 0.60, 0.25, 0.35), fc=(3200, 1100), res=0.3, uni=3, spread=0.45, drive=1.5),
    "pluck": dict(wave="saw",    env=(0.002, 0.35, 0.10, 0.28), fc=(4200, 700),  res=0.9, uni=3, spread=0.55, drive=1.6),
    "bell":  dict(wave="sine",   env=(0.002, 1.10, 0.08, 0.50), fc=(9000, 4000), res=0.0, uni=2, spread=0.70, drive=1.2),
    "stab":  dict(wave="square", env=(0.004, 0.10, 0.00, 0.07), fc=(2600, 900),  res=1.1, uni=5, spread=0.85, drive=1.8),
    "bass":  dict(wave="saw",    env=(0.006, 0.30, 0.60, 0.20), fc=(190, 105),   res=0.4, uni=1, spread=0.00, drive=2.4),
}


_NOTE_CACHE = {}


def render_note(midi, n, voice, seed=0):
    """מחזיר מערך סטריאו (n,2). המסנן נע לאורך התו — זה מה שנותן תנועה.

    התוצאה נשמרת במטמון: רצף אקורדים חוזר על עצמו עשרות פעמים לאורך שיר,
    ובלי מטמון מרנדרים את אותו תו שוב ושוב. ה-seed נגזר מהתו ומהקול בלבד
    (ולא ממיקום האקורד ברצף) — כך שהתוצאה דטרמיניסטית וגם ניתנת למטמון."""
    key = (midi, n, voice, seed)
    hit = _NOTE_CACHE.get(key)
    if hit is not None:
        return hit
    V = VOICES[voice]
    f0 = hz(midi)
    a, d, sus, r = V["env"]
    amp = S.adsr(n, a, d, sus, r, sr=SR)
    # מעטפת מסנן: נעה מהערך הראשון לשני לאורך התו
    fc0, fc1 = V["fc"]
    fc = fc0 + (fc1 - fc0) * (1.0 - np.exp(-3.2 * np.linspace(0, 1, n)))
    uni, spread = V["uni"], V["spread"]
    out = np.zeros((n, 2))
    for i in range(uni):
        off = 0.0 if uni == 1 else (i / (uni - 1) - 0.5) * 2.0
        f = f0 * 2 ** (off * 11.0 / 1200.0)          # פיזור עדין של 11 סנט
        v = S.additive(f, n, wave=V["wave"], fc=fc, res=V["res"], seed=seed + i * 31)
        out += S.pan(v, off * spread) / np.sqrt(uni)
    out *= amp[:, None]
    out = S.saturate(out, V["drive"], mix=0.6)
    _NOTE_CACHE[key] = out
    return out


def sidechain_env(n, bpm, mode, depth=0.75, release=0.18):
    if mode == "off":
        return np.ones(n)
    steps = {"four": [0, 4, 8, 12], "trap": [0, 6, 10], "pop": [0, 8]}[mode]
    return S.sidechain_env(n, bpm, steps, depth, release)


def build(seconds, bpm, key, prog, voice, bars_per_chord, octave, sidechain, seed):
    root_pc, scale = parse_key(key)
    numerals = prog.replace(",", " ").split()
    n = int(seconds * SR)
    buf = np.zeros((n, 2))                      # סטריאו מלכתחילה
    bar = 60.0 / bpm * 4.0                      # תיבה אחת ב-4/4
    dur = bar * bars_per_chord
    i = 0
    while i * dur < seconds:
        num = numerals[i % len(numerals)]
        notes = chord_midi(num, root_pc, scale, octave)
        if voice == "bass":
            notes = [notes[0] - 24]              # באס = יסוד בלבד, שתי אוקטבות למטה
            # שתיים ולא אחת: במדידה מול רפרנס אמיתי, אוקטבה אחת הותירה
            # 60% מאנרגיית הבאס בנמוך-אמצע (הבוץ) ואפס בסאב.
        pos = int(i * dur * SR)
        seg_len = min(int(dur * SR * 1.15), n - pos)   # זנב קל אל תוך האקורד הבא
        if seg_len <= 0:
            break
        for j, m in enumerate(notes):
            y = render_note(m, seg_len, voice, seed + (m * 7 + j) % 101)
            buf[pos:pos + seg_len] += y / (len(notes) ** 0.5)
        i += 1
    buf *= sidechain_env(n, bpm, sidechain)[:, None]
    return S.norm(S.limit(buf, 0.9), 0.88).astype(np.float32)


def main():
    p = argparse.ArgumentParser(description="הרמוניה ומלודיה פרוצדורליות")
    p.add_argument("--out", required=True)
    p.add_argument("--seconds", type=float, default=8.0)
    p.add_argument("--bpm", type=float, default=108.0)
    p.add_argument("--key", default="Am", help="Am, C, F#m, Ebm ...")
    p.add_argument("--prog", default="i VI III VII", help="דרגות רומיות, למשל: i VI III VII")
    p.add_argument("--voice", default="pad",
                   choices=["pad", "keys", "pluck", "bell", "stab", "bass"])
    p.add_argument("--bars", type=float, default=1.0, help="תיבות לכל אקורד")
    p.add_argument("--octave", type=int, default=3)
    p.add_argument("--sidechain", default="off", choices=["off", "four", "trap", "pop"])
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--mono", action="store_true", help="לכפות מונו (ברירת המחדל: סטריאו)")
    p.add_argument("--stereo", action="store_true", help="נשמר לתאימות — סטריאו הוא ברירת המחדל")
    a = p.parse_args()

    y = build(a.seconds, a.bpm, a.key, a.prog, a.voice, a.bars, a.octave, a.sidechain, a.seed)
    if a.mono:
        y = y.mean(axis=1)
    sf.write(a.out, y, SR, subtype="PCM_16")
    print(f"נכתב: {a.out}  {a.seconds}s @ {a.bpm} BPM, {a.key}, "
          f"קול={a.voice}, רצף={a.prog}, סייד-צ׳יין={a.sidechain}")


if __name__ == "__main__":
    main()
