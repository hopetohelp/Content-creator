#!/usr/bin/env bash
# smoke.sh — בדיקת קצה-לקצה של כל שרשרת ההפקה (שלב 8).
# מוכיחה שכל החוליות עובדות יחד לפני שמייצרים תוכן אמיתי:
#   shot.js (Chromium) -> ffmpeg (תנועה+שכבות) -> heb_ass.py (כתובית) -> tts.py + beat.py (אודיו)
set -euo pipefail
cd "$(dirname "$0")/.."
R=tests; T=/tmp/smoke; mkdir -p "$T"
echo "── 1/6  רקע: HTML → PNG (2x) דרך Chromium"
cat > "$T/bg.html" <<'HTML'
<!doctype html><meta charset="utf-8"><style>
@font-face{font-family:JB;src:url('file:///workspace/content-creator/fonts/JetBrainsMono[wght].ttf')}
html,body{margin:0;height:100%;background:#0b0b0f;overflow:hidden}
.term{position:absolute;inset:6% 8%;background:#121218;border:1px solid #23232e;border-radius:10px;
 padding:34px 40px;font-family:JB;font-size:26px;line-height:1.75;color:#8b8b9c;
 box-shadow:0 40px 120px #000a}
.g{color:#3ddc84}.r{color:#ff2d55}.y{color:#ffc857}.d{color:#4a4a58}
.bar{position:absolute;left:8%;right:8%;bottom:9%;height:10px;background:#1c1c26;border-radius:5px}
.fill{position:absolute;inset:0;width:10%;background:linear-gradient(90deg,#ff2d55,#ff6b3d);border-radius:5px}
.scan{position:absolute;inset:0;background:repeating-linear-gradient(0deg,#fff0 0 3px,#0000000f 3px 4px)}
</style>
<div class="term">
<div><span class="g">$</span> claude --resume <span class="d">session_0x8f21</span></div>
<div class="d">· reading context ......... <span class="g">ok</span></div>
<div class="d">· tokens used ............ <span class="y">90%</span></div>
<div class="d">· tokens remaining ....... <span class="r">10%</span></div>
<div class="d">· est. turns left ........ <span class="r">2</span></div>
<div><span class="g">$</span> <span class="d">_</span></div>
</div>
<div class="bar"><div class="fill"></div></div><div class="scan"></div>
HTML
node tools/shot.js "$T/bg.html" "$T/bg.png" 1920 1080 2

echo "── 2/6  שכבת גרפיקה נפרדת (שקופה): 10% במונוספייס"
cat > "$T/gfx.html" <<'HTML'
<!doctype html><meta charset="utf-8"><style>
@font-face{font-family:JB;src:url('file:///workspace/content-creator/fonts/JetBrainsMono[wght].ttf')}
html,body{margin:0;height:100%;background:transparent}
.n{position:absolute;top:8%;right:7%;font-family:JB;font-weight:800;font-size:190px;color:#ff2d55;
 letter-spacing:.02em;text-shadow:0 0 40px #ff2d5588,0 0 120px #ff2d5544;
 direction:ltr;unicode-bidi:isolate}
</style><div class="n">10%</div>
HTML
node tools/shot.js "$T/gfx.html" "$T/gfx.png" 1920 1080 2 --transparent

echo "── 3/6  אודיו אמיתי: Kokoro (3 שניות) + ביט פרוצדורלי (5 שניות)"
python3 tools/tts.py --text "Ten percent left on the meter and the screen goes dark." \
  --out "$T/vox.wav" --seconds 3 >/dev/null
python3 tools/beat.py --out "$T/beat.wav" --seconds 5 --bpm 150 --stereo >/dev/null
ffmpeg -hide_banner -loglevel error -y -i "$T/beat.wav" -i "$T/vox.wav" \
  -filter_complex "[0:a]volume=0.5[b];\
[1:a]aresample=44100,pan=stereo|c0=c0|c1=c0,adelay=700|700,apad[v];\
[b][v]amix=inputs=2:duration=first:dropout_transition=0,alimiter=limit=0.95[a]" \
  -map "[a]" -t 5 -c:a pcm_s16le "$T/mix.wav"

echo "── 4/6  כתובית עברית דרך heb_ass.py"
python3 tools/heb_ass.py --text 'נשארו לי עשרה אחוז טוקנים, וזה נגמר.' --out "$T/smoke.ass" >/dev/null

echo "── 5/6  הרכבה: תנועה (Ken Burns) + שכבת גרפיקה + כתובית צרובה"
ffmpeg -hide_banner -loglevel error -y \
  -loop 1 -t 5 -i "$T/bg.png" \
  -loop 1 -t 5 -i "$T/gfx.png" \
  -i "$T/mix.wav" \
  -filter_complex "\
[0:v]scale=2400:-1,zoompan=z='min(zoom+0.0009,1.15)':d=125:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1920x1080:fps=25,setsar=1[bg];\
[1:v]scale=1920:1080,format=rgba,fade=t=in:st=0.5:d=0.35:alpha=1,fade=t=out:st=4.2:d=0.5:alpha=1[gfx];\
[bg][gfx]overlay=0:0:format=auto[v1];\
[v1]subtitles=$T/smoke.ass:fontsdir=./fonts[v2];\
[v2]format=yuv420p[v]" \
  -map "[v]" -map 2:a -c:v libx264 -preset medium -crf 18 -pix_fmt yuv420p \
  -c:a aac -b:a 192k -movflags +faststart -t 5 "$R/smoke.mp4"

echo "── 6/6  חילוץ פריים מאמצע הקליפ"
ffmpeg -hide_banner -loglevel error -y -ss 2.5 -i "$R/smoke.mp4" -frames:v 1 -update 1 "$R/smoke_frame.png"
echo "✓ נוצר: $R/smoke.mp4  +  $R/smoke_frame.png"
