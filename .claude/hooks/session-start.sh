#!/usr/bin/env bash
# אתחול סשן — מריץ אוטומטית בכל פתיחת סשן.
# מטרתו אחת: שסשן חדש לא יתחיל לעבוד לפני שהוא יודע מה כבר נעשה,
# מה תפוס עכשיו, והאם הסביבה בכלל מותקנת.
cd "${CLAUDE_PROJECT_DIR:-$(dirname "$0")/../..}" || exit 0

echo "════════════════════════════════════════════════════"
echo " אתחול סשן — $(date -u +'%Y-%m-%d %H:%M UTC')"
echo "════════════════════════════════════════════════════"

echo
echo "── 1) מצב Git ──"
timeout 25 git fetch -q origin main 2>/dev/null && echo "origin/main נמשך" || echo "⚠️ משיכת origin/main לא הושלמה (רשת) — להמשיך בזהירות"
echo "ענף נוכחי: $(git branch --show-current 2>/dev/null)"
behind=$(git rev-list --count HEAD..origin/main 2>/dev/null || echo 0)
ahead=$(git rev-list --count origin/main..HEAD 2>/dev/null || echo 0)
echo "מרחק מ-origin/main: $ahead קדימה, $behind מאחור"
if [ -n "$(git status --porcelain 2>/dev/null)" ]; then
  echo "⚠️ יש שינויים לא-מחויבים:"; git status --short | head -10
  echo "   ← אלה תוצרים שטרם נשמרו. להריץ: bash tools/checkpoint.sh \"<תיאור>\""
else
  echo "עץ העבודה נקי"
fi

echo
echo "── 2) הסביבה מותקנת? (הקונטיינר חד-פעמי) ──"
missing=0
check() { if timeout 15 bash -c "$2" >/dev/null 2>&1; then echo "  ✓ $1"; else echo "  ✗ $1"; missing=1; fi; }
check "ffmpeg עם libass" "ffmpeg -version | grep -q enable-libass"
check "פונט Rubik"       "fc-match Rubik | grep -qi rubik"
check "Chromium"         "test -d /opt/pw-browsers"
# בדיקת חבילות פייתון בשאילתת מטא-דאטה ולא ב-import: import של torch/kokoro
# לוקח עשרות שניות ואסור שאתחול סשן ייתקע עליו.
pkgs=$(timeout 15 python3 -c "
import importlib.util as u
for m in ['numpy','soundfile','torch','kokoro']:
    print(('  \u2713 ' if u.find_spec(m) else '  \u2717 ')+m)
" 2>/dev/null)
if [ -n "$pkgs" ]; then echo "$pkgs"; echo "$pkgs" | grep -q "✗" && missing=1
else echo "  ✗ פייתון לא נענה"; missing=1; fi
if [ "$missing" = "1" ]; then
  echo
  echo "  ⛔ הסביבה חסרה. **להריץ עכשיו, לפני כל דבר אחר:**"
  echo "     bash tools/bootstrap.sh"
else
  echo "  הסביבה מוכנה."
fi

echo
echo "── 3) מצב ההפקה (PROGRESS.md) ──"
if [ -f PROGRESS.md ]; then
  grep -E "^\*\*עדכון אחרון" PROGRESS.md | sed 's/\*\*//g;s/^/  /'
  echo
  inprog=$(grep -E "^\| [0-9]+ \|" PROGRESS.md | grep "🔵" || true)
  if [ -n "$inprog" ]; then
    echo "  🔵 תפוס כרגע ע\"י סשן אחר — אין לגעת:"
    echo "$inprog" | awk -F'|' '{printf "     שלב %s — %s (סשן %s, %s)\n",$2,$3,$5,$6}'
  else
    echo "  אין שלב תפוס כרגע."
  fi
  echo
  nxt=$(grep -E "^\| [0-9]+ \|" PROGRESS.md | awk -F'|' '$4 ~ /^ *— *$/ {print; exit}')
  if [ -n "$nxt" ]; then
    echo "$nxt" | awk -F'|' '{printf "  ← השלב הפנוי הבא: %s — %s\n",$2,$3}'
    echo "     לתפוס לפני העבודה הראשונה:  bash tools/claim.sh <מספר>"
  else
    echo "  כל השלבים הושלמו או תפוסים."
  fi
  done_n=$(grep -cE "^\| [0-9]+ \|.*✅" PROGRESS.md || true)
  echo "  הושלמו: ${done_n:-0} שלבים"
fi

echo
echo "── 4) כללי הברזל של הסשן ──"
echo "  🔴 איסור גורף: אין נשים ואין קול אישה בשום תוצר — כולל בדיקות,"
echo "     דוגמאות, מדריכים ומחקרים. tts.py חוסם קול נשי מעצמו."
echo "  • להריץ bootstrap.sh אם הסביבה חסרה — לפני כל דבר אחר."
echo "  • לתפוס שלב (claim.sh) לפני הפעולה הראשונה, לא אחריה."
echo "  • צ'קפוינט אחרי כל שוט/קטע/קובץ אודיו. מה שלא נדחף — נעלם."
echo "  • תוצרי הפקה נדחפים ישירות ל-main. שינויי כלים/הנחיות — בענף + PR."
echo "  • ההנחיות המלאות: CLAUDE.md"
echo "════════════════════════════════════════════════════"
