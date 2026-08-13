#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""arrange.py — אוטומציית עוצמה על ציר הזמן, לכל סטם בנפרד.

**למה זה קיים ולא `mixdown.py --arrange`:** ה-`--arrange` של mixdown מחלק את
השיר למקטעים **שווים באורכם** (`--bars` תיבות לכל מקטע). זה מתאים לדאנס.
לקליפ עם תסריט אין מקטעים שווים: הפתיחה הקרה היא 8 שניות, הדממה שלפני
הפזמון היא תיבה אחת, וירידת הביט נופלת על שנייה 64 בדיוק. הכלי הזה מקבל
**מפה על ציר הזמן** ומיישם אותה לכל סטם.

מה זה עושה בפועל: מכפיל כל סטם במעטפת עוצמה, עם פיד-אין/אאוט קצר בכל גבול
כדי שלא יישמעו קליקים. זה, ולא יותר. המיקס עצמו נשאר ב-`mixdown.py`.

מבנה קובץ המפה (JSON):
{
  "stems": {
    "drums": {"file": "…/drums.wav", "default_db": -90,
              "ranges": [[8.0, 64.0, 0.0], [65.6, 89.6, 0.0]]}
  }
}
`default_db` = העוצמה מחוץ לכל טווח מוגדר (‎-90 = שקט מעשי).
כל טווח: [שנייה_התחלה, שנייה_סוף, רווח_dB].

שימוש:
    python3 tools/arrange.py --map arrangement.json --outdir assets/audio/arranged
"""
import argparse, io, json, os, sys

import numpy as np
import soundfile as sf

SR = 44100
FADE_MS = 8.0          # פיד בכל גבול טווח — מונע קליקים
SILENT_DB = -90.0


def db_to_lin(db):
    return 0.0 if db <= SILENT_DB else float(10.0 ** (db / 20.0))


def build_envelope(n_samples, default_db, ranges):
    """מעטפת עוצמה לדגימה־לדגימה, עם פיד קצר בכל גבול."""
    env = np.full(n_samples, db_to_lin(default_db), dtype=np.float64)
    fade = max(1, int(SR * FADE_MS / 1000.0))

    for start_s, end_s, gain_db in ranges:
        i0 = max(0, int(round(start_s * SR)))
        i1 = min(n_samples, int(round(end_s * SR)))
        if i1 <= i0:
            continue
        target = db_to_lin(gain_db)
        env[i0:i1] = target

        # פיד-אין מהערך שקדם לטווח אל ערך הטווח
        f = min(fade, i1 - i0)
        prev = env[i0 - 1] if i0 > 0 else target
        if prev != target:
            env[i0:i0 + f] = np.linspace(prev, target, f)
        # פיד-אאוט אל ערך ברירת המחדל, אם הטווח לא נוגע בסוף הקובץ
        if i1 < n_samples:
            nxt = db_to_lin(default_db)
            if nxt != target:
                f2 = min(fade, i1 - i0)
                env[i1 - f2:i1] = np.linspace(target, nxt, f2)
    return env


def apply_to_stem(path, out_path, default_db, ranges):
    y, sr = sf.read(path, always_2d=True, dtype="float64")
    if sr != SR:
        raise SystemExit(f"⛔ {path}: קצב דגימה {sr} במקום {SR}. להמיר לפני.")
    env = build_envelope(len(y), default_db, ranges)
    y = y * env[:, None]
    sf.write(out_path, y, SR, subtype="PCM_16")
    # מדידה — לא להסתמך על כך שהפקודה רצה
    peak = float(np.max(np.abs(y))) if len(y) else 0.0
    return len(y) / SR, peak


def main():
    p = argparse.ArgumentParser(description="אוטומציית עוצמה על ציר הזמן")
    p.add_argument("--map", required=True, help="קובץ JSON של המפה")
    p.add_argument("--outdir", required=True)
    a = p.parse_args()

    spec = json.load(io.open(a.map, encoding="utf-8"))
    os.makedirs(a.outdir, exist_ok=True)

    failures = []
    for name, cfg in spec["stems"].items():
        out = os.path.join(a.outdir, f"{name}.wav")
        dur, peak = apply_to_stem(cfg["file"], out, cfg.get("default_db", 0.0),
                                  cfg.get("ranges", []))
        state = "✅" if peak > 1e-4 else "⛔ שקט"
        if peak <= 1e-4:
            failures.append(name)
        print(f"  {state} {name}: {dur:.2f}s, שיא {20*np.log10(max(peak,1e-9)):.1f} dBFS -> {out}")

    if failures:
        print(f"⛔ סטמים שיצאו שקטים לגמרי: {', '.join(failures)}", file=sys.stderr)
        sys.exit(1)
    print(f"נכתב: {len(spec['stems'])} סטמים מסודרים ב-{a.outdir}")


if __name__ == "__main__":
    main()
