#!/usr/bin/env bash
# checkpoint.sh — שומר את כל ההתקדמות לריפו. **להריץ אחרי כל שלב משמעותי.**
#
# למה זה קיים: הקונטיינר חד-פעמי. כל שוט, קובץ אודיו או קטע וידאו שלא
# נדחף לריפו נעלם ברגע שהסשן נגמר או נקטע. צ'קפוינט = ההתקדמות שרדה.
#
# מתי להריץ: אחרי כל שוט שצולם, כל קטע שרונדר, כל קובץ אודיו שנוצר.
# עדיף פעם ביותר מדי מאשר פעם אחת פחות מדי — קומיט עולה שניות, סשן שנקטע
# עולה שעות.
#
# שימוש:  bash tools/checkpoint.sh "12 שוטים צולמו"
set -euo pipefail
source "$(dirname "$0")/_git_common.sh"
cd "$REPO_ROOT"

DESC="${1:?צריך תיאור. דוגמה: bash tools/checkpoint.sh \"5 קטעים רונדרו\"}"
SID="$(session_id)"; TS="$(now_utc)"

# רישום ביומן הצ'קפוינטים שבלוח
python3 - "$TS" "$SID" "$DESC" <<'PY'
import sys, io
ts, sid, desc = sys.argv[1:4]
p = "PROGRESS.md"; s = io.open(p, encoding="utf-8").read()
row = f"| {ts} | {sid} | {desc} |\n"
key = "| זמן (UTC) | סשן | מה נשמר |\n|---|---|---|\n"
s = s.replace(key, key + row, 1) if key in s else s + "\n" + row
import re
s = re.sub(r"\*\*עדכון אחרון:\*\*.*", f"**עדכון אחרון:** {ts} UTC · **סשן:** {sid}", s, count=1)
io.open(p, "w", encoding="utf-8").write(s)
PY

echo "צ'קפוינט: $DESC"
$GIT status --short | head -15
push_with_sync "צ'קפוינט: $DESC ($SID)"
