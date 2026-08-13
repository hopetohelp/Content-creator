#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
beat.py — ביט פרוצדורלי, מסונתז מאפס. אפס תלות במודלים, אפס רשת, אפס GPU,
דטרמיניסטי לחלוטין (seed קבוע -> אותו קובץ בדיוק).

זו רשת הביטחון של שכבה C לאודיו: גם אם כל מנוע יצירה אחר ייפול, יש ביט.

🔴 התופים בשכבות, לא בצליל אחד. המדידה על הגרסה הראשונה הראתה 0.1% אנרגיה
בפס הנוכחות (2–6kHz) — כי קיק שהוא סינוס בלבד פשוט אין לו שם כלום. כל תוף
כאן מורכב מקליק (גבוה), גוף (אמצע) וסאב (נמוך), בדיוק כמו בהפקה אמיתית.
הפלט **סטריאו אמיתי** — האטים והכלים פרושים, לא מונו משוכפל.

--style: התבניות מגיעות מ-`מסמכים/מחקר/` ואומתו במדידה ישירה.
   rap   — 130–150 BPM. סנר פעם אחת בתיבה (פעמה 3) = תחושת חצי-קצב
   pop   — 102–115 BPM. קיק על 1 ו-3, מחיאה על 2 ו-4, קיק קצר
   house — 124–128 BPM. ארבע-על-הרצפה, האט פתוח על האוף-ביט, באס מתגלגל
   legacy— הצליל והתבנית שלפני שדרוג הסינתזה. משוחזר בדיוק, לתוצרים ישנים

שימוש:
  python3 tools/beat.py --out beat.wav --seconds 30 --bpm 140 --style rap
  python3 tools/beat.py --out house.wav --seconds 30 --bpm 126 --style house
"""
import argparse, os, sys
import numpy as np, soundfile as sf

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import synth as S

SR = S.SR


# ── תופים בשכבות ────────────────────────────────────────────────────────────
def kick(dur=0.60, f0=185.0, f1=47.0, click=0.55, drive=1.9, seed=1):
    """שלוש שכבות: קליק (טרנזיינט גבוה), גוף (גלישת תדר), וסאב.
    הקליק הוא מה שנשמע ברמקול של טלפון; הסאב הוא מה שנשמע במערכת גדולה."""
    n = int(dur * SR); t = np.arange(n) / SR
    # גוף: גלישת תדר מהירה מ-f0 ל-f1
    f = f1 + (f0 - f1) * np.exp(-26 * t)
    body = np.sin(S.TWO_PI * np.cumsum(f) / SR) * S.perc_env(n, 0.0006, dur, curve=5.0)
    # סאב: תו נמוך ויציב מתחת לגוף
    sub = np.sin(S.TWO_PI * f1 * 0.92 * t) * S.perc_env(n, 0.004, dur, curve=3.2) * 0.75
    # קליק: פרץ רעש קצר בפס הנוכחות — זה מה שנותן "חוד"
    nc = int(0.012 * SR)
    ck = S.band_noise(nc, 1400, 6500, seed=seed) * S.perc_env(nc, 0.0002, 0.012, curve=22)
    out = body + sub
    out[:nc] += ck * click
    return S.saturate(out, drive) * 0.95


def snare(dur=0.30, seed=2):
    """גוף טונלי + רעש. שני רכיבים נפרדים, כמו סנר אמיתי."""
    n = int(dur * SR); t = np.arange(n) / SR
    body = (np.sin(S.TWO_PI * 190 * t) + 0.7 * np.sin(S.TWO_PI * 295 * t)) \
           * S.perc_env(n, 0.0008, dur, curve=13) * 0.5
    nz = S.band_noise(n, 800, 9500, seed=seed) * S.perc_env(n, 0.0006, dur, curve=8) * 0.9
    return S.saturate(body + nz, 1.5) * 0.62


def clap(dur=0.38, seed=7):
    """ארבעה פרצי רעש צפופים + זנב חדר — התחושה של כמה ידיים, לא מכה אחת."""
    n = int(dur * SR)
    out = np.zeros(n)
    for i, d in enumerate((0.0, 0.009, 0.018, 0.026)):
        k = int(d * SR)
        if k >= n:
            break
        seg = S.band_noise(n - k, 900, 5200, seed=seed + i) \
              * S.perc_env(n - k, 0.0003, 0.020, curve=26)
        out[k:] += seg * (1.0 - i * 0.16)
    tail = S.band_noise(n, 1100, 4200, seed=seed + 9) * S.perc_env(n, 0.002, dur, curve=6) * 0.30
    return S.saturate(out * 0.55 + tail, 1.3) * 0.6


_HAT_RATIOS = (2.0, 3.0, 4.16, 5.43, 6.79, 8.21)   # היחסים הלא-הרמוניים של ה-808


def hat(dur=0.055, open_=False, seed=3):
    """האט מתכתי: שישה מתנדים ביחסים לא-הרמוניים דרך מסנן גבוה — בדיוק
    השיטה של ה-TR-808. רעש לבן מסונן לבדו נשמע כמו "תססס", לא כמו האט."""
    d = dur * (5.0 if open_ else 1.0)
    n = int(d * SR); t = np.arange(n) / SR
    sig = np.zeros(n)
    for i, r in enumerate(_HAT_RATIOS):
        sig += np.sign(np.sin(S.TWO_PI * 263.0 * r * t + i))     # גל מרובע
    sig = S.band_noise(n, 6000, 17000, seed=seed) * 0.35 + sig * 0.22
    X = np.fft.rfft(sig); f = np.fft.rfftfreq(n, 1 / SR)
    sig = np.fft.irfft(X * (f > 5200), n=n)                      # מעביר-גבוה
    return sig * S.perc_env(n, 0.0003, d, curve=4.5 if open_ else 16.0) * 0.40


def sub(dur, note_hz=55.0, drive=1.5):
    n = int(dur * SR); t = np.arange(n) / SR
    y = np.sin(S.TWO_PI * note_hz * t) + 0.22 * np.sin(S.TWO_PI * note_hz * 2 * t)
    return S.saturate(y * S.perc_env(n, 0.006, dur, curve=2.4), drive) * 0.55


# ── סינתזה ישנה — משמשת אך ורק ל---style legacy ─────────────────────────────
def _v1_env(n, attack, decay, curve=3.0):
    a = max(1, int(attack * SR)); d = max(1, n - a)
    return np.concatenate([np.linspace(0, 1, a), np.exp(-curve * np.linspace(0, 1, d))])[:n]


def _v1_kick(dur=0.55, f0=120.0, f1=42.0):
    n = int(dur * SR); t = np.arange(n) / SR
    f = f1 + (f0 - f1) * np.exp(-14 * t)
    sig = np.sin(S.TWO_PI * np.cumsum(f) / SR) * _v1_env(n, 0.002, dur, 4.5)
    click = np.random.default_rng(1).normal(0, 1, n) * _v1_env(n, 0.0005, 0.012, 60) * 0.25
    return np.tanh((sig + click) * 1.6) * 0.95


def _v1_snare(dur=0.22, seed=2):
    n = int(dur * SR); t = np.arange(n) / SR
    noise = np.random.default_rng(seed).normal(0, 1, n)
    hp = np.concatenate([[0], np.diff(noise)])
    tone = (np.sin(S.TWO_PI * 185 * t) + 0.6 * np.sin(S.TWO_PI * 330 * t))
    return (hp * 0.75 + tone * 0.35) * _v1_env(n, 0.001, dur, 9) * 0.7


def _v1_hat(dur=0.055, open_=False, seed=3):
    n = int(dur * (2.8 if open_ else 1.0) * SR)
    noise = np.random.default_rng(seed).normal(0, 1, n)
    hp = noise - np.convolve(noise, np.ones(6) / 6, mode="same")
    return hp * _v1_env(n, 0.0004, dur, 22 if not open_ else 6) * 0.32


def _v1_sub(dur, note_hz=55.0):
    n = int(dur * SR); t = np.arange(n) / SR
    return np.sin(S.TWO_PI * note_hz * t) * _v1_env(n, 0.01, dur, 2.2) * 0.5


# ── סגנונות ─────────────────────────────────────────────────────────────────
# hat_div: 1 = האט בכל שש-עשירית · 2 = בכל שמינית
STYLES = {
    "rap":    dict(kick={0, 6, 10}, snare={8},        open={14}, use_clap=False,
                   hat_div=1, kick_dur=0.60, kick_f=(185.0, 47.0),
                   rolls=True,  rolling_sub=False, sidechain=False, swing=0.012),
    "pop":    dict(kick={0, 8},     snare={4, 12},    open=set(), use_clap=True,
                   hat_div=2, kick_dur=0.30, kick_f=(210.0, 58.0),
                   rolls=False, rolling_sub=False, sidechain=False, swing=0.008),
    "house":  dict(kick={0, 4, 8, 12}, snare={4, 12}, open={2, 6, 10, 14}, use_clap=True,
                   kick_dur=0.24, kick_f=(230.0, 60.0), hat_div=1,
                   rolls=False, rolling_sub=True,  sidechain=True, swing=0.0),
    "legacy": dict(kick={0, 6, 10}, snare={4, 12},    open={14}, use_clap=False,
                   hat_div=2, kick_dur=0.55, kick_f=(120.0, 42.0),
                   rolls=False, rolling_sub=False, sidechain=False, swing=0.0),
}


def mix_at(buf, sample, pos, p=0.0):
    """מערבב דגימת מונו לתוך באפר סטריאו במיקום נתון, עם פאנינג."""
    if pos < 0:                       # ההסטה האנושית עלולה להקדים לפני אפס
        sample = sample[-pos:]
        pos = 0
    end = min(len(buf), pos + len(sample))
    if pos >= len(buf) or end <= pos:
        return
    buf[pos:end] += S.pan(sample[:end - pos], p)


def build(seconds=3.0, bpm=150.0, seed=0, style="rap"):
    if style not in STYLES:
        raise SystemExit(f"⛔ סגנון לא מוכר: '{style}'. מותר: {', '.join(STYLES)}")
    C = STYLES[style]
    legacy = style == "legacy"
    n = int(seconds * SR)
    drums = np.zeros((n, 2))      # תופים — לא מושפעים מסייד-צ׳יין
    bass = np.zeros((n, 2))       # באס — כן מושפע
    spb = 60.0 / bpm
    step = spb / 4.0
    total = int(seconds / step) + 1
    rng = np.random.default_rng(seed + 777)

    for s in range(total):
        m = s % 16
        bar = s // 16
        # סווינג קל + הסטה אנושית: בלי זה הביט נשמע מכני
        jitter = 0.0 if legacy else (C["swing"] * (m % 2) + rng.normal(0, 0.0016))
        pos = int((s * step + jitter) * SR)
        vel = 1.0 if legacy else float(np.clip(rng.normal(1.0, 0.055), 0.8, 1.2))

        if m in C["kick"]:
            k = _v1_kick(C["kick_dur"], *C["kick_f"]) if legacy \
                else kick(C["kick_dur"], *C["kick_f"], seed=seed + m)
            mix_at(drums, k * vel, pos)
            if not C["rolling_sub"]:
                sb = _v1_sub(spb * 0.9, 55.0 if m != 10 else 49.0) if legacy \
                     else sub(spb * 0.9, 55.0 if m != 10 else 49.0)
                mix_at(bass, sb, pos)
        if C["rolling_sub"] and s % 2 == 0:
            mix_at(bass, sub(step * 1.7, 55.0 if m % 8 else 49.0), pos)
        if m in C["snare"]:
            if legacy:
                mix_at(drums, _v1_snare(seed=2 + m), pos)
            else:
                d = clap(seed=7 + m) if C["use_clap"] else snare(seed=2 + m)
                mix_at(drums, d * vel, pos, p=0.05 if m % 8 else -0.05)
        if s % C["hat_div"] == 0:
            op = m in C["open"]
            h = _v1_hat(open_=op, seed=3 + m) if legacy else hat(open_=op, seed=3 + m)
            amp = (1.0 if m % 4 == 0 else 0.72) * vel
            # פאנינג מתחלף — פותח את המרכז לווקאל ולקיק
            mix_at(drums, h * amp, pos, p=0.0 if legacy else (0.26 if (s // 2) % 2 else -0.26))
        if C["rolls"] and bar % 4 == 3 and m in (14, 15):
            for k in range(4):
                mix_at(drums, hat(0.035, seed=40 + m * 4 + k) * 0.55,
                       pos + int(k * step / 4 * SR), p=(-0.3 if k % 2 else 0.3))

    if C["sidechain"]:
        bass *= S.sidechain_env(n, bpm, C["kick"], depth=0.78)[:, None]
    out = drums + bass
    if legacy:
        mono = out.mean(axis=1)
        peak = np.max(np.abs(mono)) or 1.0
        return (np.tanh(mono / peak * 1.25) * 0.89).astype(np.float32)
    out = S.saturate(out, 1.25, mix=0.55)
    return S.norm(S.limit(out, 0.92), 0.92).astype(np.float32)


def main():
    p = argparse.ArgumentParser(description="ביט פרוצדורלי")
    p.add_argument("--out", required=True); p.add_argument("--seconds", type=float, default=3.0)
    p.add_argument("--bpm", type=float, default=150.0); p.add_argument("--seed", type=int, default=0)
    p.add_argument("--style", default="rap", choices=list(STYLES))
    p.add_argument("--mono", action="store_true", help="לכפות מונו (ברירת המחדל: סטריאו)")
    p.add_argument("--stereo", action="store_true", help="נשמר לתאימות לאחור — סטריאו הוא ברירת המחדל")
    a = p.parse_args()
    y = build(a.seconds, a.bpm, a.seed, a.style)
    if y.ndim == 2 and a.mono:
        y = y.mean(axis=1)
    if y.ndim == 1 and not a.mono and a.style != "legacy":
        y = np.stack([y, y], axis=1)
    sf.write(a.out, y, SR, subtype="PCM_16")
    ch = "מונו" if y.ndim == 1 else "סטריאו"
    print(f"נכתב: {a.out}  {a.seconds}s @ {a.bpm} BPM, סגנון={a.style}, {SR}Hz, {ch}")


if __name__ == "__main__":
    main()
