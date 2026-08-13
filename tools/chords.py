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
import argparse, numpy as np, soundfile as sf

SR = 44100

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
def adsr(n, a, d, s, r, curve=3.0):
    """מעטפת אמפליטודה. a/d/r בשניות, s ברמה 0..1."""
    a = max(1, int(a * SR)); d = max(1, int(d * SR)); r = max(1, int(r * SR))
    sus = max(0, n - a - d - r)
    env = np.concatenate([
        np.linspace(0, 1, a),
        s + (1 - s) * np.exp(-curve * np.linspace(0, 1, d)),
        np.full(sus, s),
        s * np.exp(-curve * np.linspace(0, 1, r)),
    ])
    return np.resize(env, n) if len(env) < n else env[:n]


def lowpass(x, cutoff):
    """מסנן מעביר-נמוך מסדר ראשון. מספיק לעיצוב צליל, זול מאוד."""
    if cutoff >= SR / 2:
        return x
    a = np.exp(-2 * np.pi * cutoff / SR)
    y = np.empty_like(x)
    acc = 0.0
    for i in range(len(x)):                       # לולאה מפורשת: IIR רקורסיבי
        acc = (1 - a) * x[i] + a * acc
        y[i] = acc
    return y


def _partials(voice):
    """(יחס תדר, משקל) לכל קול. יחסים לא-שלמים = צליל פעמון."""
    return {
        "pad":   [(1, 1.0), (2, 0.30), (3, 0.14), (4, 0.07)],
        "keys":  [(1, 1.0), (2, 0.45), (3, 0.22), (5, 0.08)],
        "pluck": [(1, 1.0), (2, 0.35), (3, 0.18)],
        "bell":  [(1, 1.0), (2.76, 0.42), (5.40, 0.18)],
        "stab":  [(1, 1.0), (2, 0.40), (3, 0.20), (4, 0.10)],
        "bass":  [(1, 1.0), (2, 0.12)],
    }[voice]


def _shape(voice, dur):
    """(מעטפת, ניתוק-בקצה, מסנן) לכל קול."""
    return {
        "pad":   (dict(a=0.35, d=0.30, s=0.80, r=0.45), 2200),
        "keys":  (dict(a=0.004, d=0.55, s=0.28, r=0.30), 3800),
        "pluck": (dict(a=0.002, d=0.45, s=0.14, r=0.25), 3200),
        "bell":  (dict(a=0.002, d=0.90, s=0.10, r=0.40), 6000),
        "stab":  (dict(a=0.004, d=0.12, s=0.00, r=0.06), 2600),
        "bass":  (dict(a=0.006, d=0.25, s=0.55, r=0.18), 900),
    }[voice]


def render_note(midi, n, voice, detune_cents=0.0, seed=0):
    """n הוא מספר דגימות ולא שניות — כדי שלא ייווצר הפרש של דגימה בעיגול."""
    t = np.arange(n) / SR
    env_kw, cut = _shape(voice, n / SR)
    f0 = hz(midi) * 2 ** (detune_cents / 1200.0)
    sig = np.zeros(n)
    for ratio, w in _partials(voice):
        phase = np.random.default_rng(seed + int(ratio * 97)).uniform(0, 2 * np.pi)
        sig += w * np.sin(2 * np.pi * f0 * ratio * t + phase)
    sig *= adsr(n, **env_kw)
    return lowpass(sig, cut)


def sidechain_env(n, bpm, mode, depth=0.72, release=0.16):
    """מעטפת סייד-צ׳יין: צניחה בכל פעימת קיק ועלייה חזרה.
    זו "הנשימה" של האוס — ראה `מסמכים/מחקר/5. הנחיה — דאנס אלקטרוני (האוס).md`."""
    if mode == "off":
        return np.ones(n)
    spb = 60.0 / bpm
    step = spb / 4.0
    hits = {"four": [0, 4, 8, 12], "trap": [0, 6, 10], "pop": [0, 8]}[mode]
    env = np.ones(n)
    rel = max(1, int(release * SR))
    ramp = 1.0 - depth * np.exp(-4.0 * np.linspace(0, 1, rel))
    for s in range(int(n / (step * SR)) + 1):
        if s % 16 in hits:
            p = int(s * step * SR)
            end = min(n, p + rel)
            if p < n:
                env[p:end] = np.minimum(env[p:end], ramp[:end - p])
    return env


def build(seconds, bpm, key, prog, voice, bars_per_chord, octave, sidechain, seed):
    root_pc, scale = parse_key(key)
    numerals = prog.replace(",", " ").split()
    n = int(seconds * SR)
    buf = np.zeros(n)
    bar = 60.0 / bpm * 4.0                      # תיבה אחת ב-4/4
    dur = bar * bars_per_chord
    i = 0
    while i * dur < seconds:
        num = numerals[i % len(numerals)]
        notes = chord_midi(num, root_pc, scale, octave)
        if voice == "bass":
            notes = [notes[0] - 12]              # באס = יסוד בלבד, אוקטבה למטה
        pos = int(i * dur * SR)
        seg_len = min(int(dur * SR * 1.15), n - pos)   # זנב קל אל תוך האקורד הבא
        if seg_len <= 0:
            break
        for j, m in enumerate(notes):
            for det in ((-6.0, 6.0) if voice in ("pad", "stab") else (0.0,)):
                y = render_note(m, seg_len, voice, det, seed + i * 13 + j)
                buf[pos:pos + seg_len] += y / (len(notes) ** 0.5)
        i += 1
    buf *= sidechain_env(n, bpm, sidechain)
    peak = np.max(np.abs(buf)) or 1.0
    return (np.tanh(buf / peak * 1.05) * 0.82).astype(np.float32)


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
    p.add_argument("--stereo", action="store_true")
    a = p.parse_args()

    y = build(a.seconds, a.bpm, a.key, a.prog, a.voice, a.bars, a.octave, a.sidechain, a.seed)
    if a.stereo:
        y = np.stack([y, y], axis=1)
    sf.write(a.out, y, SR, subtype="PCM_16")
    print(f"נכתב: {a.out}  {a.seconds}s @ {a.bpm} BPM, {a.key}, "
          f"קול={a.voice}, רצף={a.prog}, סייד-צ׳יין={a.sidechain}")


if __name__ == "__main__":
    main()
