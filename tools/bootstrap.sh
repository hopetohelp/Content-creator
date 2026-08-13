#!/usr/bin/env bash
# bootstrap.sh — משחזר את כל סביבת ההפקה בקונטיינר חדש.
# הקונטיינר חד-פעמי: ffmpeg, חבילות פייתון, פונטים ומודלים נעלמים איתו.
# הריפו שורד. הסקריפט הזה מגשר על הפער. אידמפוטנטי — אפשר להריץ שוב ושוב.
set -euo pipefail
cd "$(dirname "$0")/.."
echo "── ffmpeg + fontconfig + espeak-ng + docopt + כלים מוזיקליים"
# python3-docopt דרך apt במכוון: בניית הגלגל של docopt נכשלת על setuptools של אובונטו
apt-get update -qq
DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
  ffmpeg fontconfig espeak-ng libsndfile1 python3-docopt \
  fluidsynth fluid-soundfont-gm mma

echo "── חבילות פייתון"
pip3 install --break-system-packages -q faster-whisper python-bidi pillow numpy soundfile
# torch מהאינדקס של CPU בלבד — ברירת המחדל גוררת ~3.5GB של CUDA שאין בו שום צורך
pip3 install --break-system-packages -q torch --index-url https://download.pytorch.org/whl/cpu
pip3 install --break-system-packages -q kokoro

echo "── פונטים ברמת מערכת"
mkdir -p /usr/local/share/fonts/music-clip
cp fonts/*.ttf /usr/local/share/fonts/music-clip/
fc-cache -f >/dev/null

echo "── אימות"
test -f /usr/share/sounds/sf2/FluidR3_GM.sf2 && echo "סאונדפונט: FluidR3_GM (MIT) מותקן"
mma --help >/dev/null 2>&1 && echo "MMA: $(ls /usr/share/mma/lib/stdlib/*.mma | wc -l) קובצי סגנון"
ffmpeg -version | head -1
ffmpeg -version | tr ' ' '\n' | grep -E 'libass|fribidi' | sort -u
fc-match Rubik -f '%{family} | %{file}\n'
python3 -c "import torch,soundfile,numpy,PIL;print('python ok, torch',torch.__version__)"
echo "── בדיקת שפיות ל-RTL"
python3 tools/rtl_probe.py Rubik
echo "✓ הסביבה שוחזרה. להרצה מלאה: bash tests/smoke.sh"
