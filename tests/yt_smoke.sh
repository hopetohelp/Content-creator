#!/usr/bin/env bash
# yt_smoke.sh — בדיקת קצה-לקצה של כלי היוטיוב.
# מוכיחה: קריאת תגובות (כולל דפדוף בין עמודים), כתיבת תגובה ותשובה,
# תרגום שגיאות לעברית, בניית קישור ההרשאה, ושערי הבטיחות של ההעלאה.
#
# הקריאות מול שרת הדמה tests/yt_mock_api.py — אין צורך במפתח ולא נשרפת מכסה.
# בדיקה 8 היא היחידה שיוצאת לרשת האמיתית.
set -euo pipefail
cd "$(dirname "$0")/.."
PORT=8765
BASE="http://127.0.0.1:$PORT"
T=tests/yt_out; mkdir -p "$T"
pass() { echo "  ✓ $1"; }
fail() { echo "  ✗ $1"; exit 1; }

echo "── מפעיל שרת דמה על פורט $PORT"
python3 tests/yt_mock_api.py $PORT & MOCK=$!
trap 'kill $MOCK 2>/dev/null || true' EXIT
for _ in $(seq 30); do
  curl -s -o /dev/null "$BASE/commentThreads?key=x&videoId=T" && break || sleep 0.2
done

echo "── 1/8  קריאת תגובות, עמוד בודד"
YOUTUBE_API_KEY=mock python3 tools/yt_comments.py --video TESTVID --max 5 \
  --api-base "$BASE" > "$T/read5.txt"
grep -q "נמצאו 5 תגובות" "$T/read5.txt" || fail "לא נמצאו 5 תגובות"
grep -q "תגובה מספר 0" "$T/read5.txt" || fail "הטקסט העברי לא נפענח"
pass "5 תגובות נקראו ופוענחו"

echo "── 2/8  דפדוף: 250 תגובות = 3 עמודים (100+100+50)"
YOUTUBE_API_KEY=mock python3 tools/yt_comments.py --video TESTVID --max 250 \
  --api-base "$BASE" --json --out "$T/read250.json" >/dev/null
N=$(python3 -c "import json;print(len(json.load(open('$T/read250.json'))))")
[ "$N" = "250" ] || fail "התקבלו $N תגובות במקום 250"
LAST=$(python3 -c "import json;print(json.load(open('$T/read250.json'))[-1]['id'])")
[ "$LAST" = "MOCKID0249" ] || fail "התגובה האחרונה שגויה: $LAST"
pass "250 תגובות דרך 3 עמודים, הסדר נשמר"

echo "── 3/8  עצירה נכונה כשהמאגר קטן מהבקשה"
YOUTUBE_API_KEY=mock python3 tools/yt_comments.py --video TESTVID --max 400 \
  --api-base "$BASE" --json --out "$T/read400.json" >/dev/null
N=$(python3 -c "import json;print(len(json.load(open('$T/read400.json'))))")
[ "$N" = "250" ] || fail "אמור לעצור על 250, התקבל $N"
pass "עוצר בסוף המאגר בלי לולאה אינסופית"

echo "── 4/8  שגיאה מתורגמת לעברית: תגובות מושבתות"
OUT=$(YOUTUBE_API_KEY=mock python3 tools/yt_comments.py --video DISABLED \
  --api-base "$BASE" 2>&1 || true)
echo "$OUT" | grep -q "התגובות מושבתות" || fail "אין תרגום לעברית: $OUT"
pass "commentsDisabled → הסבר בעברית"

echo "── 5/8  שגיאה מתורגמת: אין מפתח כלל"
OUT=$(env -u YOUTUBE_API_KEY -u YT_REFRESH_TOKEN python3 tools/yt_comments.py \
  --video TESTVID --api-base "$BASE" 2>&1 || true)
echo "$OUT" | grep -q "YOUTUBE_API_KEY" || fail "אין הכוונה למפתח: $OUT"
pass "חסר מפתח → הסבר מה להגדיר"

echo "── 6/8  כתיבת תגובה ותשובה (OAuth מדומה)"
cat > "$T/fake_auth.py" <<'PY'
def access_token(): return "FAKE_TOKEN"
PY
OUT=$(PYTHONPATH="$T" python3 -c "
import sys; sys.path.insert(0,'$T')
import importlib, fake_auth
sys.modules['yt_auth'] = fake_auth
sys.argv = ['x','--video','TESTVID','--post','שלום','--api-base','$BASE']
sys.path.insert(0,'tools'); importlib.import_module('yt_comments').main()")
echo "$OUT" | grep -q "MOCKNEW_top" || fail "תגובה עליונה לא נכתבה: $OUT"
OUT=$(python3 -c "
import sys; sys.path.insert(0,'$T')
import importlib, fake_auth
sys.modules['yt_auth'] = fake_auth
sys.argv = ['x','--reply-to','MOCKID0001','--post','תשובה','--api-base','$BASE']
sys.path.insert(0,'tools'); importlib.import_module('yt_comments').main()")
echo "$OUT" | grep -q "MOCKNEW_reply" || fail "תשובה לא נכתבה: $OUT"
pass "תגובה עליונה ותשובה — שתיהן נשלחו נכון"

echo "── 7/8  שערי הבטיחות של ההעלאה"
head -c 2048 /dev/urandom > "$T/fake.mp4"
YT_CLIENT_ID=x YT_CLIENT_SECRET=y python3 tools/yt_upload.py --file "$T/fake.mp4" \
  --title "בדיקה" --tags "a,b" --dry-run > "$T/dry.txt"
grep -q '"privacyStatus": "private"' "$T/dry.txt" || fail "ברירת המחדל אינה private"
grep -q '"categoryId": "10"' "$T/dry.txt" || fail "קטגוריה שגויה"
pass "בדיקה יבשה מייצרת מטא-דאטה תקין"

OUT=$(python3 tools/yt_upload.py --file "$T/fake.mp4" --title "x" 2>&1 || true)
echo "$OUT" | grep -q "i-know-the-risk" || fail "אין שער אישור סיכון: $OUT"
pass "העלאה בלי --i-know-the-risk נחסמת"

: > "$T/empty.mp4"
OUT=$(python3 tools/yt_upload.py --file "$T/empty.mp4" --title "x" --dry-run 2>&1 || true)
echo "$OUT" | grep -q "ריק" || fail "קובץ ריק לא נתפס: $OUT"
OUT=$(python3 tools/yt_upload.py --file "$T/fake.mp4" \
  --title "$(python3 -c 'print("א"*101)')" --dry-run 2>&1 || true)
echo "$OUT" | grep -q "ארוכה מדי" || fail "כותרת ארוכה לא נתפסה: $OUT"
pass "קובץ ריק וכותרת ארוכה נתפסים לפני הרשת"

echo "── 8/8  קישור ההרשאה + מגע אמיתי ביוטיוב"
URL=$(YT_CLIENT_ID=test123 python3 tools/yt_auth.py --auth-url | tail -1)
for frag in "client_id=test123" "access_type=offline" "prompt=consent" \
            "youtube.upload" "youtube.force-ssl"; do
  echo "$URL" | grep -q "$frag" || fail "חסר בקישור: $frag"
done
pass "קישור ההרשאה מכיל את כל הרכיבים הנדרשים"

# קריאה אנונימית ליוטיוב האמיתי. אין בסביבה אישור, ולכן התשובה הנכונה היא
# דחייה מנומקת — וזו בדיוק ההוכחה שהכתובת והפרוטוקול נכונים ושהגענו לגוגל
# עצמה ולא לשגיאת רשת או לעמוד ביניים.
CODE=$(curl -s -o "$T/live.json" -w "%{http_code}" \
  "https://www.googleapis.com/youtube/v3/commentThreads?part=snippet&videoId=jNQXAC9IVRw&maxResults=1")
[ -s "$T/live.json" ] || fail "אין תשובה מיוטיוב — בעיית רשת"
case "$CODE" in
  401|403) ;;
  *) fail "תשובה לא צפויה מיוטיוב: HTTP $CODE" ;;
esac
python3 - "$T/live.json" <<'PY' || fail "הגוף שחזר אינו שגיאת YouTube API תקנית"
import json, sys
msg = json.load(open(sys.argv[1]))["error"]["message"]
assert "API Key" in msg or "authentication" in msg or "identity" in msg, msg
print(f"  יוטיוב האמיתי דחה כצפוי: {msg[:70]}...")
PY
pass "הגענו ליוטיוב האמיתי וקיבלנו דחייה מנומקת (חסר אישור בסביבה)"

echo ""
echo "✓ כל הבדיקות עברו. תוצרים: $T/"
