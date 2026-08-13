#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
loudness.py — מד עוצמה לפי תקן ITU-R BS.1770-4 / EBU R128, ב-numpy בלבד.

למה הכלי הזה קיים: `מסמכים/מחקר/2. הנחיה מרכזית` קובע יעדים מספריים
(‏-10 עד -7 LUFS, ‏True Peak מתחת ל-1-). בלי מדידה הם סיסמה.
זה הכלי שהופך אותם לשער עובר/נכשל.

🔴 זה מיישם את העיקרון של `CLAUDE.md` סעיף 6 על אודיו: **האוזן מתרגלת לעוצמה
תוך שניות ומפסיקה לשפוט אותה.** מודדים, לא מנחשים.

מה נמדד:
  LUFS משולב  — העוצמה הנתפסת של כל הרצועה, עם השערים של התקן
  LUFS קצר-טווח — המקסימום בחלון של 3 שניות
  True Peak   — השיא האמיתי, בדגימת-יתר פי 4 (מה שקורה אחרי המרה ל-MP3)
  LRA         — טווח העוצמה (כמה הרצועה "נושמת")
  Crest       — היחס בין השיא ל-RMS. קירוב לצפיפות, לא מד DR רשמי

🔴 **למדוד את הקובץ הסופי, לא את ה-WAV שלפניו.** נמדד כאן: מקודד AAC ב-160k
הוסיף 3.8dB ל-True Peak והקפיץ אותו מעל אפס. ב-320k התוספת נעלמה כמעט.
לכן לאודיו סופי — לא פחות מ-256k, ולמדוד את ה-mp4/m4a עצמו.

שימוש:
  python3 tools/loudness.py output/final.mp4 --target clip
  python3 tools/loudness.py mix.wav --target rap      # שער עובר/נכשל
  python3 tools/loudness.py a.wav b.wav               # השוואה
  python3 tools/loudness.py --selftest                # אימות המד מול התקן
"""
import argparse, os, subprocess, sys, tempfile
import numpy as np

# יעדי הז׳אנרים — מתוך `מסמכים/מחקר/2. הנחיה מרכזית — כללים לכל הסגנונות.md`
TARGETS = {
    "rap":   dict(lufs=(-10.0, -7.0), tp=-1.0),
    "pop":   dict(lufs=(-10.0, -7.0), tp=-1.0),
    "house": dict(lufs=(-10.0, -7.0), tp=-1.0),
    "clip":  dict(lufs=(-16.0, -12.0), tp=-1.0),   # קליפ לוידאו: יוטיוב מנרמל ל-14-
}


# ── שקלול K לפי BS.1770 ─────────────────────────────────────────────────────
# הפרמטרים מגיעים מהתקן עצמו. הצורה היא טרנספורם בילינארי עם K=tan(πf/fs) —
# זו הצורה שמשחזרת את המקדמים המפורסמים ב-48kHz בדיוק, ומכלילה לכל קצב דגימה.
def _shelf(sr, f0=1681.974450955533, gain_db=3.999843853973347, q=0.7071752369554196):
    """מדף-גבוה — שלב 1 של שקלול K (מדמה את השפעת הראש והאוזן)."""
    K = np.tan(np.pi * f0 / sr)
    Vh = 10.0 ** (gain_db / 20.0)
    Vb = Vh ** 0.4996667741545416
    d = 1.0 + K / q + K * K
    b = np.array([(Vh + Vb * K / q + K * K) / d,
                  2.0 * (K * K - Vh) / d,
                  (Vh - Vb * K / q + K * K) / d])
    a = np.array([1.0,
                  2.0 * (K * K - 1.0) / d,
                  (1.0 - K / q + K * K) / d])
    return b, a


def _highpass(sr, f0=38.13547087602444, q=0.5003270373238773):
    """מעביר-גבוה — שלב 2 של שקלול K (מנטרל תדרים נמוכים שלא נשמעים)."""
    K = np.tan(np.pi * f0 / sr)
    d = 1.0 + K / q + K * K
    b = np.array([1.0, -2.0, 1.0])          # המונה בתקן הוא בדיוק (1 - z⁻¹)²
    a = np.array([1.0,
                  2.0 * (K * K - 1.0) / d,
                  (1.0 - K / q + K * K) / d])
    return b, a


def k_weight(x, sr):
    """מיישם את שני המסננים בתחום התדר.

    למה בתחום התדר ולא ברקורסיה: לולאת IIR בפייתון על מיליוני דגימות איטית
    מדי, ו-scipy אינו מותקן כאן. הכפלה בתגובת התדר המדויקת שקולה מתמטית,
    ומהירה פי אלף. ריפוד באפסים מונע גלישה מעגלית."""
    n = len(x)
    pad = 8192                       # תגובת ההלם דועכת הרבה לפני זה
    N = n + pad
    f = np.fft.rfftfreq(N, 1.0 / sr)
    z = np.exp(-2j * np.pi * f / sr)
    H = np.ones_like(z)
    for b, a in (_shelf(sr), _highpass(sr)):
        H *= (b[0] + b[1] * z + b[2] * z ** 2) / (a[0] + a[1] * z + a[2] * z ** 2)
    return np.fft.irfft(np.fft.rfft(x, n=N) * H, n=N)[:n]


def _block_loudness(ch_k, sr, win, hop):
    """עוצמה לכל בלוק: l = -0.691 + 10log10(Σ z_i). מחזיר (l, z) לכל בלוק."""
    w, h = int(win * sr), int(hop * sr)
    n = min(len(c) for c in ch_k)
    if n < w:
        return np.array([]), np.zeros((len(ch_k), 0))
    starts = np.arange(0, n - w + 1, h)
    z = np.empty((len(ch_k), len(starts)))
    for i, c in enumerate(ch_k):
        sq = c ** 2
        cs = np.concatenate([[0.0], np.cumsum(sq)])
        z[i] = (cs[starts + w] - cs[starts]) / w      # ממוצע ריבועי לכל בלוק
    tot = z.sum(axis=0)
    with np.errstate(divide="ignore"):
        l = -0.691 + 10 * np.log10(np.where(tot > 0, tot, 1e-30))
    return l, z


def integrated_lufs(ch_k, sr):
    """LUFS משולב עם שני השערים של התקן: מוחלט ב-70- ויחסי ב-10- LU."""
    l, z = _block_loudness(ch_k, sr, 0.400, 0.100)
    if l.size == 0:
        return float("nan")
    keep = l > -70.0                                   # שער מוחלט
    if not keep.any():
        return float("nan")
    tot = z[:, keep].mean(axis=1).sum()
    gamma = -0.691 + 10 * np.log10(max(tot, 1e-30)) - 10.0   # שער יחסי
    keep &= l > gamma
    if not keep.any():
        return float("nan")
    tot = z[:, keep].mean(axis=1).sum()
    return -0.691 + 10 * np.log10(max(tot, 1e-30))


def short_term_max(ch_k, sr):
    l, _ = _block_loudness(ch_k, sr, 3.0, 0.100)
    return float(l.max()) if l.size else float("nan")


def loudness_range(ch_k, sr):
    """LRA לפי EBU R128: בלוקים של 3 שניות, שער יחסי ב-20- LU, אחוזון 10–95."""
    l, z = _block_loudness(ch_k, sr, 3.0, 1.0)
    if l.size == 0:
        return float("nan")
    keep = l > -70.0
    if not keep.any():
        return float("nan")
    tot = z[:, keep].mean(axis=1).sum()
    gamma = -0.691 + 10 * np.log10(max(tot, 1e-30)) - 20.0
    sel = l[keep & (l > gamma)]
    if sel.size < 2:
        return 0.0
    return float(np.percentile(sel, 95) - np.percentile(sel, 10))


def true_peak_dbtp(ch, sr, oversample=4):
    """שיא אמיתי בדגימת-יתר פי 4. עובד במקטעים כדי לא לפוצץ את הזיכרון.

    למה זה חשוב: הדגימות עצמן יכולות להיות מתחת ל-0 dBFS בעוד שהגל *שביניהן*
    חורג. אחרי המרה ל-MP3/AAC החריגה הזאת הופכת לעיוות ששומעים.

    ℹ️ ההשוואה מול `ffmpeg -filter_complex ebur128=peak=true` תראה הפרש של
    ~0.2dB: ffmpeg משתמש במסנן FIR פוליפאזי, וכאן זו אינטרפולציית sinc מלאה.
    הכיוון בטוח — המדידה כאן מחמירה יותר, ולכן שער שעובר כאן יעבור גם שם."""
    peak = 0.0
    seg, ov = 1 << 18, 256
    for c in ch:
        for s in range(0, len(c), seg):
            blk = c[max(0, s - ov): s + seg + ov]
            if len(blk) < 8:
                peak = max(peak, float(np.max(np.abs(blk))) if len(blk) else 0.0)
                continue
            up = np.fft.irfft(np.fft.rfft(blk), n=len(blk) * oversample) * oversample
            peak = max(peak, float(np.max(np.abs(up))))
    return 20 * np.log10(peak) if peak > 0 else -np.inf


# ── קלט ─────────────────────────────────────────────────────────────────────
def load(path):
    """קורא WAV ישירות; כל שאר הפורמטים (mp4, mp3, m4a) דרך ffmpeg."""
    import soundfile as sf
    if path.lower().endswith((".wav", ".flac", ".ogg", ".aiff", ".aif")):
        y, sr = sf.read(path, always_2d=True)
        return [y[:, i].astype(np.float64) for i in range(y.shape[1])], sr
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as t:
        tmp = t.name
    try:
        r = subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", path,
                            "-map", "a:0", "-c:a", "pcm_f32le", tmp],
                           capture_output=True, text=True)
        if r.returncode != 0 or os.path.getsize(tmp) == 0:
            raise SystemExit(f"⛔ ffmpeg לא הצליח לחלץ אודיו מ-{path}\n{r.stderr.strip()}")
        y, sr = sf.read(tmp, always_2d=True)
        return [y[:, i].astype(np.float64) for i in range(y.shape[1])], sr
    finally:
        os.path.exists(tmp) and os.unlink(tmp)


def measure(path):
    ch, sr = load(path)
    if not ch or len(ch[0]) == 0:
        raise SystemExit(f"⛔ אין אודיו ב-{path} (קובץ ריק או ללא ערוץ קול)")
    ch_k = [k_weight(c, sr) for c in ch]
    rms = float(np.sqrt(np.mean(np.concatenate(ch) ** 2)))
    pk = float(np.max([np.max(np.abs(c)) for c in ch]))
    return dict(
        path=path, sr=sr, channels=len(ch), seconds=len(ch[0]) / sr,
        lufs=integrated_lufs(ch_k, sr),
        short=short_term_max(ch_k, sr),
        lra=loudness_range(ch_k, sr),
        tp=true_peak_dbtp(ch, sr),
        peak_db=20 * np.log10(pk) if pk > 0 else -np.inf,
        crest=(20 * np.log10(pk / rms) if rms > 0 and pk > 0 else float("nan")),
        silent=pk < 1e-4,
    )


def report(m, target=None):
    print(f"\n── {m['path']}")
    chans = "מונו" if m["channels"] == 1 else "סטריאו" if m["channels"] == 2 \
            else f"{m['channels']} ערוצים"
    print(f"   {m['seconds']:.2f} שניות · {m['sr']}Hz · {chans}")
    if m["silent"]:
        print("   🔴 הקובץ שקט לחלוטין — זה כישלון, גם אם הפקודה החזירה 0.")
        return False
    print(f"   LUFS משולב   : {m['lufs']:7.2f}")
    print(f"   LUFS קצר-טווח: {m['short']:7.2f}   (מקסימום בחלון 3 שניות)")
    print(f"   True Peak    : {m['tp']:7.2f} dBTP")
    print(f"   שיא דגימה    : {m['peak_db']:7.2f} dBFS")
    print(f"   LRA          : {m['lra']:7.2f} LU    (טווח עוצמה)")
    print(f"   Crest        : {m['crest']:7.2f} dB    (שיא מול RMS)")
    if m["channels"] == 1:
        print("   ℹ️  קובץ מונו נמדד ~3dB נמוך יותר מאותו תוכן בסטריאו. זה תקין לפי התקן.")
    if not target:
        return True
    t = TARGETS[target]
    lo, hi = t["lufs"]
    ok_l = lo <= m["lufs"] <= hi
    ok_p = m["tp"] < t["tp"]
    print(f"\n   שער '{target}':")
    print(f"   {'✅' if ok_l else '❌'} LUFS בין {lo} ל-{hi}  → {m['lufs']:.2f}")
    print(f"   {'✅' if ok_p else '❌'} True Peak מתחת ל-{t['tp']} → {m['tp']:.2f}")
    if not ok_l:
        print(f"      ↳ {'חלש מדי — להעלות' if m['lufs'] < lo else 'חזק מדי — להנמיך'} "
              f"בערך {abs(m['lufs'] - (lo if m['lufs'] < lo else hi)):.1f} dB")
    if not ok_p:
        print("      ↳ להוריד את הלימיטר. עוצמה תחרותית היא 80% סידור — לא לימיטר חזק יותר.")
    return ok_l and ok_p


def main():
    p = argparse.ArgumentParser(description="מד עוצמה BS.1770 / EBU R128")
    p.add_argument("files", nargs="*")
    p.add_argument("--target", choices=list(TARGETS), help="שער עובר/נכשל לפי ז׳אנר")
    p.add_argument("--selftest", action="store_true", help="אימות המד מול התקן")
    a = p.parse_args()
    if a.selftest:
        sys.exit(0 if selftest() else 1)
    if not a.files:
        p.error("צריך לפחות קובץ אחד (או --selftest)")
    ok = True
    for f in a.files:
        ok &= report(measure(f), a.target)
    sys.exit(0 if ok else 1)


# ── אימות עצמי ──────────────────────────────────────────────────────────────
def selftest():
    """מאמת את המד מול שני עוגנים חיצוניים.
    זה בדיוק הכלל של `CLAUDE.md` סעיף 6: לאמת את הבדיקה לפני שמאמינים לה."""
    ok = True
    print("── 1/2  מקדמי המסננים מול הערכים המפורסמים בתקן (48kHz)")
    REF_SHELF_B = [1.53512485958697, -2.69169618940638, 1.19839281085285]
    REF_SHELF_A = [1.0, -1.69065929318241, 0.73248077421585]
    REF_HP_B    = [1.0, -2.0, 1.0]
    REF_HP_A    = [1.0, -1.99004745483398, 0.99007225036621]
    for name, (b, a), rb, ra in [("מדף-גבוה", _shelf(48000), REF_SHELF_B, REF_SHELF_A),
                                 ("מעביר-גבוה", _highpass(48000), REF_HP_B, REF_HP_A)]:
        db = float(np.max(np.abs(np.array(b) - rb)))
        da = float(np.max(np.abs(np.array(a) - ra)))
        good = db < 1e-6 and da < 1e-6
        ok &= good
        print(f"   {'✅' if good else '❌'} {name}: סטייה מרבית b={db:.2e} a={da:.2e}")

    print("── 2/2  אות הבדיקה של EBU: סינוס 1kHz ב-23- dBFS בסטריאו ⇒ 23.0- LUFS")
    for sr in (44100, 48000):
        t = np.arange(int(sr * 10)) / sr
        amp = 10 ** (-23.0 / 20.0)
        x = amp * np.sin(2 * np.pi * 1000 * t)
        chk = [k_weight(x, sr), k_weight(x, sr)]
        got = integrated_lufs(chk, sr)
        good = abs(got - (-23.0)) < 0.1                # הסובלנות של EBU Tech 3341
        ok &= good
        print(f"   {'✅' if good else '❌'} {sr}Hz: נמדד {got:.3f} LUFS (סטייה {got + 23.0:+.3f})")

    print("\n" + ("✅ המד מאומת מול התקן" if ok else "❌ המד אינו תואם את התקן"))
    return ok


if __name__ == "__main__":
    main()
