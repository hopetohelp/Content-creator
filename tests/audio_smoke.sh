#!/usr/bin/env bash
# audio_smoke.sh — בדיקת קצה-לקצה לכלי האודיו:
#   beat.py · chords.py · band.py · mixdown.py · loudness.py
#
# 🔴 הכלל של CLAUDE.md סעיף 6: פקודה שהחזירה 0 היא לא הוכחה.
# לכן כל שלב כאן מאמת את **התוצר עצמו** — התבנית שנוגנה, הצלילים שנשמעו,
# והעוצמה שנמדדה. לא רק שהסקריפט לא קרס.
set -euo pipefail
cd "$(dirname "$0")/.."
T=/tmp/audio_smoke; mkdir -p "$T"

echo "── 1/7  מד העוצמה מול התקן (BS.1770 + אות הבדיקה של EBU)"
python3 tools/loudness.py --selftest

echo "── 2/7  beat.py — ארבעת הסגנונות, ותבנית מדודה מול התיעוד"
for s in rap pop house legacy; do
  python3 tools/beat.py --out "$T/b_$s.wav" --seconds 12 --bpm 126 --style "$s" --stereo >/dev/null
done
python3 - <<'PY'
import importlib.util
spec = importlib.util.spec_from_file_location("m", "tools/beat.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
# מה שמסמכי המחקר מבטיחים — כל שינוי בתבנית ייתפס כאן
EXPECT = {"rap":   dict(kick={0,6,10},   perc={8},    hats=16, open={14}),
          "pop":   dict(kick={0,8},      perc={4,12}, hats=8,  open=set()),
          "house": dict(kick={0,4,8,12}, perc={4,12}, hats=16, open={2,6,10,14})}
def probe(style, bpm=126.0):
    om = m.mix_at; orig = {n: getattr(m, n) for n in ("kick","snare","clap","hat","sub")}
    last, sched = {"k": None}, []
    def wrap(name, fn):
        def g(*a, **k):
            kind = "open" if (name == "hat" and k.get("open_", a[1] if len(a) > 1 else False)) \
                   else name
            last["k"] = kind; return fn(*a, **k)
        return g
    for n, fn in orig.items(): setattr(m, n, wrap(n, fn))
    m.mix_at = lambda buf, s, pos, *a, **k: (sched.append((pos, last["k"])), om(buf, s, pos, *a, **k))[1]
    m.build(seconds=60/bpm*4*2, bpm=bpm, style=style)
    m.mix_at = om
    for n, fn in orig.items(): setattr(m, n, fn)
    step = 60.0/bpm/4.0; out = {}
    for pos, kind in sched:
        out.setdefault(kind, set()).add(round((pos/m.SR)/step) % 16)
    return out
for style, e in EXPECT.items():
    g = probe(style)
    opn = g.get("open", set())
    assert g.get("kick", set()) == e["kick"],  f"{style}: קיק {sorted(g.get('kick',set()))} != {sorted(e['kick'])}"
    assert (g.get("snare",set()) | g.get("clap",set())) == e["perc"], f"{style}: סנר/מחיאה שגויים"
    assert opn == e["open"], f"{style}: האט פתוח {sorted(opn)} != {sorted(e['open'])}"
    assert len((g.get("hat",set()) | opn)) == e["hats"], f"{style}: מספר האטים שגוי"
    print(f"   ✅ {style}: תבנית תואמת את התיעוד")
PY

echo "── 3/7  chords.py — חמישה קולות, ובדיקה שהאקורדים בסולם הנכון"
for v in pad keys pluck stab bass; do
  python3 tools/chords.py --out "$T/c_$v.wav" --seconds 10 --bpm 108 --key Am \
    --prog "i VI III VII" --voice "$v" --stereo >/dev/null
done
python3 - <<'PY'
import numpy as np, soundfile as sf, importlib.util
spec = importlib.util.spec_from_file_location("ch", "tools/chords.py")
ch = importlib.util.module_from_spec(spec); spec.loader.exec_module(ch)
y, sr = sf.read("/tmp/audio_smoke/c_pad.wav")
y = y.mean(axis=1)
bar = 60.0/108.0*4
root, scale = ch.parse_key("Am")
for i, num in enumerate(["i","VI","III","VII"]):
    a = int((i*bar + 0.35)*sr); b = min(int((i*bar + bar*0.8)*sr), len(y))
    seg = y[a:b] * np.hanning(b-a)
    S = np.abs(np.fft.rfft(seg, n=1<<18)); f = np.fft.rfftfreq(1<<18, 1/sr)
    S = np.where((f > 80) & (f < 1200), S, 0)
    pk = [j for j in range(1, len(S)-1) if S[j] > S[j-1] and S[j] > S[j+1] and S[j] > 0.20*S.max()]
    found = {round(69 + 12*np.log2(f[j]/440.0)) for j in pk}
    exp = ch.chord_midi(num, root, scale, 3)
    missing = [e for e in exp if not any(abs(e-g) < 0.6 for g in found)]
    assert not missing, f"אקורד {num}: תווים חסרים {missing}"
    print(f"   ✅ {num}: כל תווי האקורד נמצאו בפועל בספקטרום")
PY

echo "── 4/7  אף קובץ אינו שקט ואינו באורך 0"
python3 - <<'PY'
import glob, numpy as np, soundfile as sf
bad = []
for p in sorted(glob.glob("/tmp/audio_smoke/*.wav")):
    y, sr = sf.read(p)
    pk = float(np.max(np.abs(y))) if y.size else 0.0
    if y.size == 0 or pk < 1e-4: bad.append((p, pk))
assert not bad, f"קבצים שקטים או ריקים: {bad}"
print(f"   ✅ כל {len(glob.glob('/tmp/audio_smoke/*.wav'))} הקבצים מכילים אודיו אמיתי")
PY

echo "── 5/7  band.py — ליווי בכלים אמיתיים מסגנון מוכן"
if command -v mma >/dev/null && command -v fluidsynth >/dev/null; then
  python3 tools/band.py --out "$T/band.wav" --style PopBallad --bpm 104 --key Am \
    --prog "i VI III VII" --repeat 1 >/dev/null
  python3 - <<'PYA'
import numpy as np, soundfile as sf
y, sr = sf.read("/tmp/audio_smoke/band.wav", always_2d=True)
assert y.size and float(np.max(np.abs(y))) > 1e-3, "band.py הפיק קובץ שקט"
corr = float(np.corrcoef(y[:, 0], y[:, 1])[0, 1])
assert corr < 0.99, f"band.py הפיק מונו (מתאם {corr:.3f})"
print(f"   \u2705 ליווי אמיתי: {len(y)/sr:.1f}s, מתאם ערוצים {corr:.3f}")
PYA
else
  echo "   MMA/fluidsynth לא מותקנים — מדלג (bash tools/bootstrap.sh מתקין)"
fi

echo "── 6/7  mixdown.py — סטם חלש ודינמי לא נעלם במיקס"
python3 - <<'PYB'
import numpy as np, soundfile as sf
sr = 44100
t = np.arange(sr * 4) / sr
quiet = (np.sin(2 * np.pi * 330 * t) * 0.02)[:, None].repeat(2, 1)
sf.write("/tmp/audio_smoke/quiet.wav", quiet, sr, subtype="PCM_16")
PYB
python3 tools/mixdown.py --out "$T/bal.wav" --target pop \
  drums="$T/b_pop.wav" harmony="$T/quiet.wav" >/dev/null
python3 - <<'PYC'
import numpy as np, soundfile as sf
y, _ = sf.read("/tmp/audio_smoke/bal.wav")
S = np.abs(np.fft.rfft(y.mean(axis=1))); f = np.fft.rfftfreq(len(y), 1 / 44100)
share = float(np.sum(S[(f > 280) & (f < 380)] ** 2)) / max(float(np.sum(S ** 2)), 1e-12)
assert share > 1e-4, f"הסטם החלש נעלם (נתח {share:.2e}) — יישור העוצמה לא עבד"
print(f"   \u2705 הסטם החלש שרד את המיקס (נתח אנרגיה {share*100:.2f}%)")
PYC

echo "── 7/7  שרשרת מלאה דרך mixdown.py — מבנה + יעד עוצמה אוטומטי"
python3 tools/beat.py   --out "$T/m_drums.wav" --seconds 24 --bpm 126 --style house >/dev/null
python3 tools/chords.py --out "$T/m_bass.wav"  --seconds 24 --bpm 126 --key Fm --prog "i VI III VII" \
  --voice bass --sidechain four >/dev/null
python3 tools/chords.py --out "$T/m_pad.wav"   --seconds 24 --bpm 126 --key Fm --prog "i VI III VII" \
  --voice pad  --octave 4 --sidechain four >/dev/null
python3 tools/chords.py --out "$T/m_stab.wav"  --seconds 24 --bpm 126 --key Fm --prog "i VI III VII" \
  --voice stab --octave 5 --bars 0.5 --sidechain four >/dev/null
python3 tools/mixdown.py --out "$T/mix.wav" --target house --bpm 126 --bars 4 \
  --arrange "intro,build,drop,drop" \
  drums="$T/m_drums.wav" bass="$T/m_bass.wav" harmony="$T/m_pad.wav" lead="$T/m_stab.wav"
python3 tools/loudness.py "$T/mix.wav" --target house --balance

echo
echo "✓ כל בדיקות האודיו עברו. התוצרים: $T/"
