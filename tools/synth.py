#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
synth.py — ספריית ה-DSP המשותפת ל-`beat.py`, `chords.py` ו-`mixdown.py`.
לא מיועדת להרצה ישירה. numpy בלבד — אפס תלות, אפס רשת, דטרמיניסטית.

🔴 למה היא נכתבה: המדידה על הדמו הראשון הראתה 0.1% אנרגיה בפס הנוכחות
(2–6kHz) ומתאם ערוצים 0.999 — כלומר סינתזת סינוסים טהורים במונו.
זה בדיוק מה שגורם לצליל להישמע חיוור וקטן. הפתרון כאן:

  1. **סינתזה אדיטיבית עם מסנן פר-הרמוניה** — מייצרת מסור/מרובע עשירים
     בהרמוניות, בלי אליאסינג, עם מסנן שמשתנה בזמן ועם רזוננס. זה מה שממלא
     את פס הנוכחות שהיה ריק.
  2. **יוניסון סטריאו** — כמה מתנדים בהיסט תדר קל, פרושים על פני התמונה.
     זה מה שהופך 0.999 מתאם לרוחב אמיתי.
  3. **תופים בשכבות** — קליק, גוף וסאב בנפרד, כמו בהפקה אמיתית.
  4. **רוויה** — מייצרת הרמוניות שלא היו, ומוסיפה נוכחות וקול "יקר".
  5. **ריוורב קונבולוציה** — מרחב. בלי מרחב הכול נשמע כמו דמו MIDI.
"""
import numpy as np

SR = 44100
TWO_PI = 2.0 * np.pi


# ── מעטפות ──────────────────────────────────────────────────────────────────
def adsr(n, a=0.005, d=0.2, s=0.4, r=0.2, sr=SR, curve=4.0):
    """מעטפת אמפליטודה בארבעה שלבים. אורך הפלט תמיד n בדיוק."""
    na, nd, nr = (max(1, int(x * sr)) for x in (a, d, r))
    ns = max(0, n - na - nd - nr)
    if na + nd + nr > n:                       # תו קצר מדי לכל השלבים
        na = max(1, int(n * 0.05)); nd = max(1, int(n * 0.35))
        nr = max(1, n - na - nd); ns = 0
    parts = [np.linspace(0.0, 1.0, na),
             s + (1.0 - s) * np.exp(-curve * np.linspace(0, 1, nd)),
             np.full(ns, s),
             s * np.exp(-curve * np.linspace(0, 1, nr))]
    e = np.concatenate(parts)
    return e[:n] if len(e) >= n else np.pad(e, (0, n - len(e)))


def perc_env(n, attack=0.0008, decay=0.25, sr=SR, curve=7.0):
    """מעטפת הקשה: עלייה מיידית, דעיכה מעריכית. לתופים."""
    na = max(1, int(attack * sr))
    nd = max(1, n - na)
    return np.concatenate([np.linspace(0, 1, na),
                           np.exp(-curve * np.linspace(0, 1, nd))])[:n]


# ── מסנן פר-הרמוניה ─────────────────────────────────────────────────────────
def filt_gain(freq, fc, res=0.0, order=2):
    """תגובת מסנן מעביר-נמוך עם רזוננס, בנקודת תדר אחת.
    fc יכול להיות סקלר או מערך (מסנן שמשתנה בזמן) — הכול וקטורי."""
    fc = np.maximum(np.asarray(fc, dtype=float), 20.0)
    r = freq / fc
    lp = 1.0 / np.sqrt(1.0 + r ** (2 * order))
    if res <= 0:
        return lp
    # התנפחות סביב תדר החיתוך = הרזוננס ששומעים
    bump = 1.0 + res * np.exp(-(np.log2(np.maximum(r, 1e-9)) ** 2) / (2 * 0.18 ** 2))
    return lp * bump


_WAVE_HARMONICS = {
    # (פונקציית משרעת לפי מספר ההרמוניה, האם רק אי-זוגיות)
    "saw":    (lambda k: 1.0 / k,            False),
    "square": (lambda k: 1.0 / k,            True),
    "tri":    (lambda k: 1.0 / (k * k),      True),
    "sine":   (lambda k: 1.0 * (k == 1),     False),
}


def additive(f0, n, wave="saw", fc=None, res=0.0, sr=SR, nharm=40, seed=0, phase_rand=True):
    """סינתזה אדיטיבית: סוכמים הרמוניות עם מסנן פר-הרמוניה.

    למה ככה ולא מתנד + מסנן רקורסיבי: לולאת IIR בפייתון איטית מדי, וגל מסור
    שנוצר ישירות גורם אליאסינג. כאן אין אליאסינג בכלל (לא מייצרים הרמוניה
    מעל נייקוויסט), המסנן יכול להשתנות בזמן בחינם, והכול וקטורי.

    המימוש בכפל חיצוני אחד (K×n) ולא בלולאה — קריאה אחת ל-C במקום עשרות."""
    amp_fn, odd_only = _WAVE_HARMONICS[wave]
    nyq = sr * 0.47
    if fc is None:
        fc = nyq
    fc_max = float(np.max(fc))
    # מגבלה אדפטיבית: הרמוניה שהמסנן מחסל ממילא לא שווה את החישוב
    kmax = int(min(nharm, nyq / max(f0, 1e-6), max(6.0, 8.0 * fc_max / max(f0, 1e-6))))
    ks = np.arange(1, max(kmax, 1) + 1)
    if odd_only:
        ks = ks[ks % 2 == 1]
    if ks.size == 0:
        return np.zeros(n)
    freqs = f0 * ks
    ks = ks[freqs <= nyq]; freqs = freqs[freqs <= nyq]
    if ks.size == 0:
        return np.zeros(n)
    amps = np.asarray([amp_fn(k) for k in ks], dtype=float)
    t = (np.arange(n) / sr).astype(np.float32)
    ph = np.random.default_rng(seed).uniform(0, TWO_PI, ks.size) if phase_rand \
         else np.zeros(ks.size)
    # (K,n) בבת אחת, ב-float32 — מחצית מתעבורת הזיכרון
    wav = np.sin(TWO_PI * np.outer(freqs.astype(np.float32), t)
                 + ph[:, None].astype(np.float32), dtype=np.float32)
    amps = amps.astype(np.float32)
    if np.ndim(fc) == 0:
        return ((amps * filt_gain(freqs, fc, res)).astype(np.float32) @ wav).astype(float)
    # מסנן נע: מחושב בבלוקים ולא לכל דגימה. מעטפת מסנן זזה בקצב של עשרות
    # מילישניות, ולכן 64 בלוקים חלקים לגמרי לאוזן — ופי כמה זולים.
    fc = np.asarray(fc, dtype=float)
    B = 64
    edges = np.linspace(0, n, B + 1).astype(int)
    out = np.empty(n, dtype=np.float32)
    for b in range(B):
        a0, a1 = edges[b], edges[b + 1]
        if a1 <= a0:
            continue
        fcb = float(fc[(a0 + a1) // 2])                # ערך החיתוך במרכז הבלוק
        gb = (amps * filt_gain(freqs, fcb, res)).astype(np.float32)
        out[a0:a1] = gb @ wav[:, a0:a1]
    return out.astype(float)


# ── רעש ─────────────────────────────────────────────────────────────────────
def noise(n, seed=0):
    return np.random.default_rng(seed).normal(0, 1, n)


def band_noise(n, lo, hi, sr=SR, seed=0):
    """רעש מסונן לפס תדרים, דרך FFT. מדויק וזול."""
    x = noise(n, seed)
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(n, 1 / sr)
    # שיפועי קצה רכים כדי שלא יישמע מסונן-דיגיטלית
    m = np.ones_like(f)
    m[f < lo] = np.clip((f[f < lo] / max(lo, 1e-9)) ** 2, 0, 1)
    m[f > hi] = np.clip((hi / np.maximum(f[f > hi], 1e-9)) ** 2, 0, 1)
    return np.fft.irfft(X * m, n=n)


# ── עיוות והרמוניות ─────────────────────────────────────────────────────────
def saturate(x, drive=1.6, mix=1.0):
    """רוויה רכה. מייצרת הרמוניות שלא היו — זה מה שמוסיף נוכחות וחום.
    בלי זה סינתזה נשמעת שטוחה גם כשהמאזן נכון."""
    if drive <= 0:
        return x
    y = np.tanh(x * drive) / np.tanh(drive)
    return x * (1 - mix) + y * mix


def exciter(x, sr=SR, freq=3000.0, amount=0.35):
    """מעורר גבהים: מעוות רק את הפס הגבוה ומחזיר אותו למיקס.
    ממלא את פס הנוכחות (2–6kHz) שבמדידה היה 0.1%."""
    n = len(x)
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(n, 1 / sr)
    hi = np.fft.irfft(X * (f > freq), n=n)
    return x + saturate(hi, 3.0) * amount


# ── סטריאו ──────────────────────────────────────────────────────────────────
def pan(x, p=0.0):
    """פאנינג בעוצמה שווה. p: -1 שמאל, 0 מרכז, 1 ימין. מחזיר (n,2)."""
    a = (p + 1) * np.pi / 4
    return np.stack([x * np.cos(a), x * np.sin(a)], axis=1)


def unison(f0, n, voices=5, detune_cents=12.0, spread=1.0, **kw):
    """כמה מתנדים בהיסט תדר קל, פרושים על פני התמונה הסטריאופונית.
    🔑 זה הכלי המרכזי נגד "מתאם ערוצים 0.999" — הוא יוצר רוחב אמיתי,
    לא הרחבה מזויפת של אות מונו."""
    out = np.zeros((n, 2))
    if voices < 1:
        voices = 1
    for i in range(voices):
        # פריסה סימטרית סביב התדר המרכזי
        off = 0.0 if voices == 1 else (i / (voices - 1) - 0.5) * 2.0
        f = f0 * 2 ** (off * detune_cents / 1200.0)
        p = off * spread
        v = additive(f, n, seed=kw.pop("seed", 0) + i * 17, **kw) if i == 0 else \
            additive(f, n, seed=i * 17 + 101, **{k: v for k, v in kw.items() if k != "seed"})
        out += pan(v, p) / np.sqrt(voices)
    return out


def widen(st, amount=0.35):
    """הרחבת בסיס Mid/Side. שומר תאימות למונו (לא מבטל את המרכז)."""
    m = (st[:, 0] + st[:, 1]) * 0.5
    s = (st[:, 0] - st[:, 1]) * 0.5 * (1.0 + amount)
    return np.stack([m + s, m - s], axis=1)


# ── מרחב ────────────────────────────────────────────────────────────────────
def reverb_ir(seconds=1.8, decay=5.5, predelay=0.012, sr=SR, seed=11, damp=0.45):
    """מייצר תגובת הלם של חדר: רעש דועך + השתקת גבהים לאורך הזנב.
    זה נותן ריוורב קונבולוציה אמיתי בלי אף קובץ חיצוני."""
    n = int(seconds * sr)
    rng = np.random.default_rng(seed)
    t = np.linspace(0, 1, n)
    env = np.exp(-decay * t)
    ir = np.stack([rng.normal(0, 1, n) * env, rng.normal(0, 1, n) * env], axis=1)
    # השתקת גבהים ככל שהזנב מתקדם — חדר אמיתי מאבד גבהים לפני נמוכים
    X = np.fft.rfft(ir, axis=0)
    f = np.fft.rfftfreq(n, 1 / sr)[:, None]
    X *= 1.0 / (1.0 + (f / (sr * 0.5 * (1 - damp))) ** 2)
    ir = np.fft.irfft(X, n=n, axis=0)
    pre = int(predelay * sr)
    ir = np.vstack([np.zeros((pre, 2)), ir])[:n]
    peak = np.max(np.abs(ir)) or 1.0
    return ir / peak


def convolve(x, ir):
    """קונבולוציה דרך FFT. x ו-ir יכולים להיות מונו או סטריאו."""
    x = x if x.ndim == 2 else np.stack([x, x], axis=1)
    ir = ir if ir.ndim == 2 else np.stack([ir, ir], axis=1)
    n = len(x) + len(ir) - 1
    N = 1 << (n - 1).bit_length()
    out = np.zeros((N, 2))
    for c in range(2):
        out[:, c] = np.fft.irfft(np.fft.rfft(x[:, c], N) * np.fft.rfft(ir[:, c], N), n=N)
    out = out[:len(x)]
    peak = np.max(np.abs(out)) or 1.0
    return out / peak


# ── דינמיקה ─────────────────────────────────────────────────────────────────
def sidechain_env(n, bpm, steps, depth=0.75, release=0.18, sr=SR):
    """מעטפת צניחה בכל פעימת קיק — "הנשימה" של הז׳אנר."""
    step = 60.0 / bpm / 4.0
    env = np.ones(n)
    rel = max(1, int(release * sr))
    ramp = 1.0 - depth * np.exp(-4.0 * np.linspace(0, 1, rel))
    for s in range(int(n / (step * sr)) + 1):
        if s % 16 in steps:
            p = int(s * step * sr)
            if p < n:
                e = min(n, p + rel)
                env[p:e] = np.minimum(env[p:e], ramp[:e - p])
    return env


def compress(x, thresh_db=-18.0, ratio=3.0, attack=0.008, release=0.12, sr=SR, makeup=True):
    """דחיסת "דבק" לאפיק. מעטפת פשוטה — מספיקה בהחלט לגלוּ באס."""
    mono = x.mean(axis=1) if x.ndim == 2 else x
    env = np.abs(mono)
    # עוקב המעטפת רקורסיבי ולכן לא ניתן לווקטוריזציה — אבל הוא זז לאט.
    # מריצים אותו על מעטפה מדוללת פי DS ואז מותחים בחזרה: פי ~50 מהר יותר,
    # והתוצאה זהה לאוזן (דוחס דבק, לא לימיטר).
    DS = 32
    m = (len(env) // DS) * DS
    coarse = env[:m].reshape(-1, DS).max(axis=1) if m else env
    sr_c = sr / DS
    aa = np.exp(-1.0 / max(attack * sr_c, 1e-6)); ar = np.exp(-1.0 / max(release * sr_c, 1e-6))
    sm_c = np.empty_like(coarse); acc = 0.0
    for i in range(len(coarse)):
        c = aa if coarse[i] > acc else ar
        acc = c * acc + (1 - c) * coarse[i]
        sm_c[i] = acc
    sm = np.interp(np.arange(len(env)), np.arange(len(sm_c)) * DS + DS / 2, sm_c)
    db = 20 * np.log10(np.maximum(sm, 1e-9))
    over = np.maximum(0.0, db - thresh_db)
    gain = 10 ** (-(over * (1 - 1 / ratio)) / 20.0)
    y = x * (gain[:, None] if x.ndim == 2 else gain)
    if makeup:
        y *= 10 ** ((thresh_db * (1 - 1 / ratio) * -0.5) / 20.0)
    return y


def _oversampled_abs(x, factor=4):
    """|האות| בדגימת-יתר, מוחזר לקצב המקורי ע"י מקסימום בכל קבוצה.
    כך הלימיטר "רואה" גם את השיאים שבין הדגימות."""
    n = len(x)
    ch = [x[:, c] for c in range(x.shape[1])] if x.ndim == 2 else [x]
    out = np.zeros(n)
    seg = 1 << 17
    for c in ch:
        for s in range(0, n, seg):
            blk = c[s:s + seg]
            if len(blk) < 8:
                out[s:s + len(blk)] = np.maximum(out[s:s + len(blk)], np.abs(blk))
                continue
            up = np.fft.irfft(np.fft.rfft(blk), n=len(blk) * factor) * factor
            m = np.abs(up[:len(blk) * factor]).reshape(len(blk), factor).max(axis=1)
            out[s:s + len(blk)] = np.maximum(out[s:s + len(blk)], m)
    return out


def limit(x, ceiling=0.89, lookahead=0.004, sr=SR, true_peak=False):
    """לימיטר עם הצצה קדימה. חותך שיאים בלי לעוות את הגוף.

    true_peak=True מודד בדגימת-יתר ×4 — כלומר התקרה חלה על ה-True Peak
    ולא רק על שיא הדגימה. זה מה שמונע חריגה אחרי קידוד ל-AAC."""
    if true_peak:
        mono = _oversampled_abs(x)
    else:
        mono = np.max(np.abs(x), axis=1) if x.ndim == 2 else np.abs(x)
    la = max(1, int(lookahead * sr))
    # השיא המרבי בחלון קדימה
    pad = np.concatenate([mono, np.zeros(la)])
    roll = np.lib.stride_tricks.sliding_window_view(pad, la).max(axis=1)[:len(mono)]
    gain = np.minimum(1.0, ceiling / np.maximum(roll, 1e-9))
    # ⚠️ החלקה לבדה מרימה בחזרה את השקע שנוצר בדיוק בשיא, והתקרה נשברת.
    # לכן קודם מינימום-גולש ברוחב ההחלקה: אחריו, כל ממוצע משוקלל בחלון
    # קטן-או-שווה לערך הנדרש בשיא — והתקרה מובטחת בלי לחתוך את כל השיר.
    w = la * 2 + 1
    pad = np.pad(gain, (w // 2, w // 2), mode="edge")
    gain = np.lib.stride_tricks.sliding_window_view(pad, w).min(axis=1)[:len(gain)]
    k = np.hanning(w); k /= k.sum()
    gain = np.convolve(gain, k, mode="same")
    return x * (gain[:, None] if x.ndim == 2 else gain)


def norm(x, peak=0.95):
    p = np.max(np.abs(x)) or 1.0
    return x * (peak / p)
