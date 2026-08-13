#!/usr/bin/env bash
# claim.sh — תופס שלב הפקה *לפני* שמתחילים לעבוד עליו.
#
# למה זה קיים: סשנים ואנשים עובדים במקביל. מי שלא תופס שלב מראש מגלה
# אחרי שעה שמישהו אחר עשה את אותו דבר. תפיסה נדחפת ל-main מיד, לפני
# הפעולה הראשונה — לא בסופה.
#
# שימוש:  bash tools/claim.sh 8              # תפיסת שלב 8
#         bash tools/claim.sh 8 --done       # סימון כהושלם
#         bash tools/claim.sh 8 --blocked "הסיבה"
#         bash tools/claim.sh 8 --free       # שחרור תפיסה תקועה
#
# תפיסה תקועה: סשן שנקטע משאיר שלב ב-"בעבודה" לנצח ואיש לא נוגע בו.
# אם התאריך בעמודת "עודכן" ישן משעתיים ואין התקדמות ביומן הצ'קפוינטים —
# לשחרר עם --free ולציין זאת בסיכום.
set -euo pipefail
source "$(dirname "$0")/_git_common.sh"
cd "$REPO_ROOT"

STEP="${1:?צריך מספר שלב. דוגמה: bash tools/claim.sh 8}"
MODE="${2:-claim}"; NOTE="${3:-}"
SID="$(session_id)"; TS="$(now_utc)"

$GIT pull --rebase --autostash -q origin main 2>/dev/null || true

case "$MODE" in
  --done)    STATUS="✅";        VERB="הושלם" ;;
  --free)    STATUS="—";         VERB="שוחרר" ;;
  --blocked) STATUS="⛔";        VERB="נחסם" ;;
  *)         STATUS="🔵 בעבודה"; VERB="נתפס" ;;
esac

# בדיקה: השלב כבר תפוס ע"י סשן אחר?
if [ "$MODE" = "claim" ]; then
  existing=$(grep -E "^\| $STEP \|" PROGRESS.md | grep "🔵 בעבודה" || true)
  if [ -n "$existing" ] && ! echo "$existing" | grep -q "$SID"; then
    echo "⛔ שלב $STEP כבר תפוס ע\"י סשן אחר:"
    echo "   $existing"
    echo "   אל תיגע בו. בחר שלב אחר, או בדוק מול הבעלים."
    exit 1
  fi
fi

python3 - "$STEP" "$STATUS" "$SID" "$TS" "$NOTE" <<'PY'
import sys, io, re
step, status, sid, ts, note = sys.argv[1:6]
p = "PROGRESS.md"; s = io.open(p, encoding="utf-8").read()
def repl(m):
    cells = [c.strip() for c in m.group(0).strip().strip("|").split("|")]
    if status == "—":
        cells[2], cells[3], cells[4] = "—", "—", "—"
    else:
        cells[2], cells[3], cells[4] = status, sid, ts
    if note: cells[5] = note
    return "| " + " | ".join(cells) + " |"
# חשוב: נספרות ההחלפות ולא מושווית המחרוזת. תפיסה חוזרת של אותו סשן באותה
# דקה מייצרת שורה זהה — השוואת מחרוזות הייתה מדווחת "השלב לא נמצא" בטעות.
s2, n = re.subn(rf"^\| {re.escape(step)} \|.*\|$", repl, s, count=1, flags=re.M)
if n == 0: sys.exit(f"לא נמצא שלב {step} ב-PROGRESS.md")
s2 = re.sub(r"\*\*עדכון אחרון:\*\*.*", f"**עדכון אחרון:** {ts} UTC · **סשן:** {sid}", s2, count=1)
io.open(p, "w", encoding="utf-8").write(s2)
PY

echo "שלב $STEP — $VERB ע\"י $SID"
push_with_sync "לוח: שלב $STEP $VERB ($SID)"
