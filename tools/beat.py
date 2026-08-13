#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
beat.py — ביט פרוצדורלי, מסונתז מאפס ב-numpy. אפס תלות במודלים,
אפס רשת, אפס GPU, דטרמיניסטי לחלוטין (seed קבוע -> אותו קובץ בדיוק).

זו רשת הביטחון של שכבה C לאודיו: גם אם כל מנוע יצירה אחר ייפול, יש ביט.

תכולה:  808 קיק מסונתז (סינוס עם גלישת תדר + קליק), סנר (רעש מסונן + טון),
        מחיאת כפיים, האי-האט סגור/פתוח, באס-ליין תת-נמוך וסייד-צ׳יין.

🔴 --style: התבניות מגיעות מ-`מסמכים/מחקר/` ואומתו במדידה ישירה.
   rap   — 130–150 BPM. סנר פעם אחת בתיבה (פעמה 3) = תחושת חצי-קצב. האטים בשש-עשיריות + גלגולים
   pop   — 102–115 BPM. קיק על 1 ו-3, מחיאה על 2 ו-4, קיק קצר (בלי גלישת 808)
   house — 124–128 BPM. ארבע-על-הרצפה, האט פתוח על האוף-ביט, באס מתגלגל + סייד-צ׳יין
   legacy— התבנית המקורית מלפני הוספת הסגנונות. משוחזרת בדיוק, לשחזור תוצרים ישנים

שימוש:
  python3 tools/beat.py --out beat.wav --seconds 30 --bpm 140 --style rap
  python3 tools/beat.py --out house.wav --seconds 30 --bpm 126 --style house --stereo
"""
import argparse, numpy as np, soundfile as sf

SR = 44100

def _env(n, attack, decay, curve=3.0):
    """מעטפת אמפליטודה: עלייה מהירה, דעיכה מעריכית."""
    a = max(1, int(attack * SR)); d = max(1, n - a)
    return np.concatenate([np.linspace(0, 1, a), np.exp(-curve * np.linspace(0, 1, d))])[:n]

def kick808(dur=0.55, f0=120.0, f1=42.0):
    """808: סינוס שתדרו גולש מ-f0 ל-f1, פלוס קליק טרנזיינט."""
    n = int(dur * SR); t = np.arange(n) / SR
    f = f1 + (f0 - f1) * np.exp(-14 * t)                 # גלישת תדר
    sig = np.sin(2 * np.pi * np.cumsum(f) / SR) * _env(n, 0.002, dur, 4.5)
    click = np.random.default_rng(1).normal(0, 1, n) * _env(n, 0.0005, 0.012, 60) * 0.25
    return np.tanh((sig + click) * 1.6) * 0.95           # רוויה קלה = חום

def snare(dur=0.22, seed=2):
    n = int(dur * SR); t = np.arange(n) / SR
    rng = np.random.default_rng(seed)
    noise = rng.normal(0, 1, n)
    # מסנן מעביר-גבוה פשוט מסדר 1
    hp = np.concatenate([[0], np.diff(noise)])
    tone = (np.sin(2*np.pi*185*t) + 0.6*np.sin(2*np.pi*330*t))
    return (hp * 0.75 + tone * 0.35) * _env(n, 0.001, dur, 9) * 0.7

def hat(dur=0.055, open_=False, seed=3):
    n = int(dur * (2.8 if open_ else 1.0) * SR)
    rng = np.random.default_rng(seed)
    noise = rng.normal(0, 1, n)
    hp = noise - np.convolve(noise, np.ones(6)/6, mode="same")   # מעביר-גבוה
    return hp * _env(n, 0.0004, dur, 22 if not open_ else 6) * 0.32

def clap(dur=0.20, seed=7):
    """מחיאת כפיים: רעש מסונן בלבד, בלי הרכיב הטונלי של הסנר.
    זה צליל הפופ/האוס של 2026 — ראה `מסמכים/מחקר/4. הנחיה — פופ.md`."""
    n = int(dur * SR)
    rng = np.random.default_rng(seed)
    noise = rng.normal(0, 1, n)
    hp = noise - np.convolve(noise, np.ones(4)/4, mode="same")   # מעביר-גבוה
    burst = _env(n, 0.001, dur, 14)
    # שלוש הקשות צפופות = התחושה של כמה ידיים
    for d in (0.010, 0.019):
        k = int(d * SR)
        burst[k:] += _env(n - k, 0.001, dur, 16) * 0.7
    return hp * burst * 0.42


def sub(dur, note_hz=55.0):
    n = int(dur * SR); t = np.arange(n) / SR
    return np.sin(2*np.pi*note_hz*t) * _env(n, 0.01, dur, 2.2) * 0.5


# ── סגנונות ─────────────────────────────────────────────────────────────────
# hat_div: 1 = האט בכל שש-עשירית · 2 = בכל שמינית
STYLES = {
    "rap":    dict(kick={0, 6, 10}, snare={8},        open={14}, use_clap=False,
                   hat_div=1, kick_dur=0.55, kick_f=(120.0, 42.0),
                   rolls=True,  rolling_sub=False, sidechain=False),
    "pop":    dict(kick={0, 8},     snare={4, 12},    open=set(), use_clap=True,
                   hat_div=2, kick_dur=0.16, kick_f=(150.0, 58.0),
                   rolls=False, rolling_sub=False, sidechain=False),
    "house":  dict(kick={0, 4, 8, 12}, snare={4, 12}, open={2, 6, 10, 14}, use_clap=True,
                   hat_div=1, kick_dur=0.12, kick_f=(160.0, 62.0),
                   rolls=False, rolling_sub=True,  sidechain=True),
    "legacy": dict(kick={0, 6, 10}, snare={4, 12},    open={14}, use_clap=False,
                   hat_div=2, kick_dur=0.55, kick_f=(120.0, 42.0),
                   rolls=False, rolling_sub=False, sidechain=False),
}


def sidechain_env(n, bpm, kick_steps, depth=0.72, release=0.16):
    """צניחה בכל פעימת קיק ועלייה חזרה — "הנשימה" של האוס."""
    step = 60.0 / bpm / 4.0
    env = np.ones(n)
    rel = max(1, int(release * SR))
    ramp = 1.0 - depth * np.exp(-4.0 * np.linspace(0, 1, rel))
    for s in range(int(n / (step * SR)) + 1):
        if s % 16 in kick_steps:
            p = int(s * step * SR)
            if p < n:
                end = min(n, p + rel)
                env[p:end] = np.minimum(env[p:end], ramp[:end - p])
    return env

def mix_at(buf, sample, pos):
    """מערבב דגימה לתוך הבאפר במיקום נתון, עם חיתוך בקצה."""
    end = min(len(buf), pos + len(sample))
    if pos >= len(buf) or end <= pos: return
    buf[pos:end] += sample[:end - pos]

def build(seconds=3.0, bpm=150.0, seed=0, style="rap"):
    if style not in STYLES:
        raise SystemExit(f"⛔ סגנון לא מוכר: '{style}'. מותר: {', '.join(STYLES)}")
    S = STYLES[style]
    np.random.default_rng(seed)
    n = int(seconds * SR)
    drums = np.zeros(n, dtype=np.float64)          # תופים — לא מושפעים מסייד-צ׳יין
    bass  = np.zeros(n, dtype=np.float64)          # באס — כן מושפע
    spb = 60.0 / bpm                 # שניות לפעימה (רבע)
    step = spb / 4.0                 # שש-עשירית
    total_steps = int(seconds / step) + 1

    for s in range(total_steps):
        pos = int(s * step * SR); m = s % 16
        bar = s // 16
        if m in S["kick"]:
            mix_at(drums, kick808(S["kick_dur"], *S["kick_f"]), pos)
            if not S["rolling_sub"]:
                mix_at(bass, sub(spb * 0.9, 55.0 if m != 10 else 49.0), pos)
        # באס מתגלגל: שמיניות רצופות במקום תו ארוך אחד (חתימת ההאוס)
        if S["rolling_sub"] and s % 2 == 0:
            mix_at(bass, sub(step * 1.7, 55.0 if m % 8 else 49.0), pos)
        if m in S["snare"]:
            mix_at(drums, clap(seed=7 + m) if S["use_clap"] else snare(seed=2 + m), pos)
        # האטים — בשש-עשיריות או בשמיניות, עם וריאציית עוצמה
        if s % S["hat_div"] == 0:
            h = hat(open_=(m in S["open"]), seed=3 + m)
            mix_at(drums, h * (1.0 if m % 4 == 0 else 0.72), pos)
        # גלגול האט לפני מעבר: כל 4 תיבות, על שתי השש-עשיריות האחרונות
        if S["rolls"] and bar % 4 == 3 and m in (14, 15):
            for k in range(4):                     # 64-יות = גלגול מהיר
                mix_at(drums, hat(0.035, seed=40 + m * 4 + k) * 0.55,
                       pos + int(k * step / 4 * SR))

    if S["sidechain"]:
        bass *= sidechain_env(n, bpm, S["kick"])
    buf = drums + bass
    peak = np.max(np.abs(buf)) or 1.0
    buf = np.tanh(buf / peak * 1.25) * 0.89        # לימיטר רך + נרמול
    return buf.astype(np.float32)

def main():
    p = argparse.ArgumentParser(description="ביט הִיפ-הופ פרוצדורלי")
    p.add_argument("--out", required=True); p.add_argument("--seconds", type=float, default=3.0)
    p.add_argument("--bpm", type=float, default=150.0); p.add_argument("--seed", type=int, default=0)
    p.add_argument("--style", default="rap", choices=list(STYLES))
    p.add_argument("--stereo", action="store_true")
    a = p.parse_args()
    y = build(a.seconds, a.bpm, a.seed, a.style)
    if a.stereo: y = np.stack([y, y], axis=1)
    sf.write(a.out, y, SR, subtype="PCM_16")
    print(f"נכתב: {a.out}  {a.seconds}s @ {a.bpm} BPM, סגנון={a.style}, "
          f"{SR}Hz, {'סטריאו' if a.stereo else 'מונו'}")

if __name__ == "__main__":
    main()
