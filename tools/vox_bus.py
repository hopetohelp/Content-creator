#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""vox_bus.py — מרכיב שורות TTS בודדות לפס ווקאל אחד, מיושר לרשת.

**זה השלב שבו נולד הראפ.** מנוע TTS הוא מנוע דיבור: הוא לא מנגן פלואו על
ביט. הפלואו נוצר מ**המיקום** — כל שורה מתחילה בדיוק בתחילת הבר שלה. ראו
`מסמכים/מחקר/3. הנחיה — ראפ.md` סעיף 9: "הראפ נולד במיקום, לא בהקראה".

מה הכלי עושה, לפי הסדר:
1. **גוזר שקט** מתחילת וסוף כל שורה. ‏TTS מוסיף שקט בקצוות, ובלי גזירה
   השורה "מתחילה" מאוחר מהבר שלה והפלואו מתפרק.
2. **מתאים לחריץ** ב-`atempo`, עד תקרה. מעבר לתקרה הקול נשמע מכני, ולכן
   מותרת גלישה אל הרווח שלפני השורה הבאה במקום להאיץ יותר.
3. **ממקם בהיסט הדגימה המדויק** של תחילת הבר.
4. **אד-ליבס** — נכנסות ב**רווח שבסוף השורה**, מוזזות לצד ובעוצמה נמוכה.
   אד-ליב שמכסה את השורה היא רעש; אד-ליב שעונה לה היא חצי מהאישיות של השיר.

שימוש:
    python3 tools/vox_bus.py --lyrics assets/audio/lyrics.json \\
        --voxdir assets/audio/vox --out assets/audio/vox_bus.wav
"""
import argparse, io, json, os, subprocess, tempfile

import numpy as np
import soundfile as sf

SR = 44100
TEMPO_MAX = 1.28          # מעבר לזה הקול נשמע מכני
TEMPO_MIN = 0.85
ADLIB_GAIN = 0.42         # ‎-7.5dB בערך
ADLIB_PAN = 0.72          # 0=מרכז, 1=צד מלא
TRIM = ("silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.02:detection=peak,"
        "areverse,"
        "silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.02:detection=peak,"
        "areverse")


def atempo_chain(ratio):
    """‎atempo מקבל 0.5–2.0 בלבד. יחס מחוץ לטווח נבנה משרשור."""
    parts, r = [], ratio
    while r > 2.0:
        parts.append("atempo=2.0"); r /= 2.0
    while r < 0.5:
        parts.append("atempo=0.5"); r /= 0.5
    parts.append(f"atempo={r:.5f}")
    return ",".join(parts)


def load_fitted(path, slot, headroom):
    """גוזר, מאיץ לפי הצורך, ומחזיר מונו ב-SR. headroom = הרווח עד השורה הבאה."""
    with tempfile.TemporaryDirectory() as td:
        trimmed = os.path.join(td, "t.wav")
        subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-af", TRIM,
                        "-ar", str(SR), "-ac", "1", trimmed, "-y"], check=True)
        y, _ = sf.read(trimmed, dtype="float64")
        dur = len(y) / SR
        budget = slot + headroom          # מותר לגלוש אל הרווח, לא אל השורה הבאה
        if dur <= budget:
            return y, dur, 1.0
        ratio = min(TEMPO_MAX, max(TEMPO_MIN, dur / budget))
        sped = os.path.join(td, "s.wav")
        subprocess.run(["ffmpeg", "-v", "error", "-i", trimmed, "-af",
                        atempo_chain(ratio), "-ar", str(SR), "-ac", "1", sped, "-y"],
                       check=True)
        y, _ = sf.read(sped, dtype="float64")
        return y, len(y) / SR, ratio


def place(bus, mono, start_s, gain=1.0, pan=0.0):
    """pan: ‎-1 שמאל, 0 מרכז, +1 ימין. חוק כוח שווה, כדי שהעוצמה לא תזוז."""
    i0 = int(round(start_s * SR))
    n = min(len(mono), len(bus) - i0)
    if n <= 0:
        return
    l = gain * np.sqrt((1.0 - pan) / 2.0) * np.sqrt(2)
    r = gain * np.sqrt((1.0 + pan) / 2.0) * np.sqrt(2)
    bus[i0:i0 + n, 0] += mono[:n] * l
    bus[i0:i0 + n, 1] += mono[:n] * r


def main():
    p = argparse.ArgumentParser(description="הרכבת פס ווקאל מיושר לרשת")
    p.add_argument("--lyrics", required=True)
    p.add_argument("--voxdir", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--seconds", type=float, default=90.0)
    a = p.parse_args()

    spec = json.load(io.open(a.lyrics, encoding="utf-8"))
    lines = spec["lines"]
    bus = np.zeros((int(a.seconds * SR), 2), dtype=np.float64)

    warn = []
    for i, l in enumerate(lines):
        slot = l["end"] - l["start"]
        nxt = lines[i + 1]["start"] if i + 1 < len(lines) else a.seconds
        headroom = max(0.0, nxt - l["end"] - 0.12)      # 120ms נשימה לפני השורה הבאה
        src = os.path.join(a.voxdir, f"{l['id']}.wav")
        mono, dur, ratio = load_fitted(src, slot, headroom)
        place(bus, mono, l["start"], gain=1.0, pan=0.0)
        flag = ""
        if dur > slot + headroom + 0.02:
            flag = "  ⚠️ עדיין ארוך מהחריץ"
            warn.append(l["id"])
        print(f"  {l['id']:8s} @{l['start']:6.2f}  חריץ {slot:4.2f}+{headroom:4.2f}  "
              f"בפועל {dur:4.2f}  tempo×{ratio:.2f}{flag}")

        if l.get("adlib"):
            ad = os.path.join(a.voxdir, f"ad_{l['id']}.wav")
            if os.path.exists(ad):
                # האד-ליב עונה לשורה: נכנסת אחריה, בתוך הרווח
                gap = max(0.0, slot - dur)
                at = l["start"] + dur + min(0.10, gap * 0.5)
                amono, _, _ = load_fitted(ad, max(0.5, gap + headroom), 0.0)
                pan = ADLIB_PAN if i % 2 == 0 else -ADLIB_PAN
                place(bus, amono, at, gain=ADLIB_GAIN, pan=pan)

    peak = float(np.max(np.abs(bus)))
    if peak > 0.99:
        bus *= 0.99 / peak
    sf.write(a.out, bus, SR, subtype="PCM_16")

    active = float((np.abs(bus).max(axis=1) > 1e-3).mean())
    print(f"\nנכתב: {a.out}  {len(bus)/SR:.2f}s  שיא {20*np.log10(max(peak,1e-9)):.1f} dBFS  "
          f"כיסוי קול {active*100:.0f}% מהזמן")
    if warn:
        print(f"⚠️ שורות שעדיין חורגות מהחריץ: {', '.join(warn)}")


if __name__ == "__main__":
    main()
