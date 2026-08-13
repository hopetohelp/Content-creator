#!/usr/bin/env bash
# audio_smoke.sh — בדיקת קצה-לקצה לכלי האודיו: beat.py, chords.py, loudness.py.
#
# 🔴 הכלל של CLAUDE.md סעיף 6: פקודה שהחזירה 0 היא לא הוכחה.
# לכן כל שלב כאן מאמת את **התוצר עצמו** — התבנית שנוגנה, הצלילים שנשמעו,
# והעוצמה שנמדדה. לא רק שהסקריפט לא קרס.
set -euo pipefail
cd "$(dirname "$0")/.."
T=/tmp/audio_smoke; mkdir -p "$T"

echo "── 1/5  מד העוצמה מול התקן (BS.1770 + אות הבדיקה של EBU)"
python3 tools/loudness.py --selftest

echo "── 2/5  beat.py — ארבעת הסגנונות, ותבנית מדודה מול התיעוד"
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
    om = m.mix_at; orig = {n: getattr(m, n) for n in ("kick808","snare","clap","hat","sub")}
    last, sched = {"k": None}, []
    def wrap(name, fn):
        def g(*a, **k):
            kind = "open" if (name == "hat" and k.get("open_", a[1] if len(a) > 1 else False)) \
                   else name
            last["k"] = kind; return fn(*a, **k)
        return g
    for n, fn in orig.items(): setattr(m, n, wrap(n, fn))
    m.mix_at = lambda buf, s, pos: (sched.append((pos, last["k"])), om(buf, s, pos))[1]
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
    assert g.get("kick808", set()) == e["kick"],  f"{style}: קיק {sorted(g.get('kick808',set()))} != {sorted(e['kick'])}"
    assert (g.get("snare",set()) | g.get("clap",set())) == e["perc"], f"{style}: סנר/מחיאה שגויים"
    assert opn == e["open"], f"{style}: האט פתוח {sorted(opn)} != {sorted(e['open'])}"
    assert len((g.get("hat",set()) | opn)) == e["hats"], f"{style}: מספר האטים שגוי"
    print(f"   ✅ {style}: תבנית תואמת את התיעוד")
PY

echo "── 3/5  chords.py — חמישה קולות, ובדיקה שהאקורדים בסולם הנכון"
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

echo "── 4/5  אף קובץ אינו שקט ואינו באורך 0"
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

echo "── 5/5  מיקס מלא (תופים+פד+סטאב) עובר את שער העוצמה"
python3 tools/beat.py   --out "$T/m_drums.wav" --seconds 24 --bpm 126 --style house --stereo >/dev/null
python3 tools/chords.py --out "$T/m_pad.wav"   --seconds 24 --bpm 126 --key Fm --prog "i VI III VII" \
  --voice pad  --sidechain four --stereo >/dev/null
python3 tools/chords.py --out "$T/m_stab.wav"  --seconds 24 --bpm 126 --key Fm --prog "i VI III VII" \
  --voice stab --bars 0.5 --sidechain four --stereo >/dev/null
ffmpeg -v error -y -i "$T/m_drums.wav" -i "$T/m_pad.wav" -i "$T/m_stab.wav" \
  -filter_complex "[0]volume=1.0[a];[1]volume=0.55[b];[2]volume=0.45[c];\
[a][b][c]amix=inputs=3:normalize=0,volume=3.6,\
alimiter=level_in=1:limit=0.66:attack=3:release=60:level=disabled,volume=0.93[o]" \
  -map "[o]" "$T/mix.wav"
python3 tools/loudness.py "$T/mix.wav" --target house

echo
echo "✓ כל בדיקות האודיו עברו. התוצרים: $T/"
