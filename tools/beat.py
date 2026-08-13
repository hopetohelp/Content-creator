#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
beat.py — ביט הִיפ-הופ פרוצדורלי, מסונתז מאפס ב-numpy. אפס תלות במודלים,
אפס רשת, אפס GPU, דטרמיניסטי לחלוטין (seed קבוע -> אותו קובץ בדיוק).

זו רשת הביטחון של שכבה C לאודיו: גם אם כל מנוע יצירה אחר ייפול, יש ביט.

תכולה:  808 קיק מסונתז (סינוס עם גלישת תדר + קליק), סנר (רעש מסונן + טון),
        האי-האט סגור/פתוח, ובאס-ליין תת-נמוך. 150 BPM כברירת מחדל.

שימוש:  python3 tools/beat.py --out assets/audio/beat.wav --seconds 3 --bpm 150
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

def sub(dur, note_hz=55.0):
    n = int(dur * SR); t = np.arange(n) / SR
    return np.sin(2*np.pi*note_hz*t) * _env(n, 0.01, dur, 2.2) * 0.5

def mix_at(buf, sample, pos):
    """מערבב דגימה לתוך הבאפר במיקום נתון, עם חיתוך בקצה."""
    end = min(len(buf), pos + len(sample))
    if pos >= len(buf) or end <= pos: return
    buf[pos:end] += sample[:end - pos]

def build(seconds=3.0, bpm=150.0, seed=0):
    np.random.default_rng(seed)
    n = int(seconds * SR); buf = np.zeros(n, dtype=np.float64)
    spb = 60.0 / bpm                 # שניות לפעימה (רבע)
    step = spb / 4.0                 # שמינית-שש-עשרה
    total_steps = int(seconds / step) + 1
    # תבנית בת 16 צעדים (בר אחד ב-4/4)
    KICK  = {0, 6, 10}
    SNARE = {4, 12}
    OPEN  = {14}
    for s in range(total_steps):
        pos = int(s * step * SR); m = s % 16
        if m in KICK:
            mix_at(buf, kick808(), pos)
            mix_at(buf, sub(spb * 0.9, 55.0 if m != 10 else 49.0), pos)
        if m in SNARE: mix_at(buf, snare(seed=2 + m), pos)
        # האטס בכל שמינית, עם סווינג קל ווריאציית עוצמה
        if s % 2 == 0:
            h = hat(open_=(m in OPEN), seed=3 + m)
            mix_at(buf, h * (1.0 if m % 4 == 0 else 0.72), pos)
    peak = np.max(np.abs(buf)) or 1.0
    buf = np.tanh(buf / peak * 1.25) * 0.89        # לימיטר רך + נרמול
    return buf.astype(np.float32)

def main():
    p = argparse.ArgumentParser(description="ביט הִיפ-הופ פרוצדורלי")
    p.add_argument("--out", required=True); p.add_argument("--seconds", type=float, default=3.0)
    p.add_argument("--bpm", type=float, default=150.0); p.add_argument("--seed", type=int, default=0)
    p.add_argument("--stereo", action="store_true")
    a = p.parse_args()
    y = build(a.seconds, a.bpm, a.seed)
    if a.stereo: y = np.stack([y, y], axis=1)
    sf.write(a.out, y, SR, subtype="PCM_16")
    print(f"נכתב: {a.out}  {a.seconds}s @ {a.bpm} BPM, {SR}Hz, {'סטריאו' if a.stereo else 'מונו'}")

if __name__ == "__main__":
    main()
