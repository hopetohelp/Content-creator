# פונקציות משותפות לכלי השמירה. לא להריץ ישירות.
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GIT="git -C $REPO_ROOT -c user.email=hopetohelp.il@gmail.com -c user.name=Claude"
session_id() { echo "${SESSION_NAME:-$(hostname 2>/dev/null || echo session)-$$}"; }
now_utc()    { date -u +"%Y-%m-%d %H:%M"; }

# דחיפה עמידה: מסנכרן מול main לפני כל ניסיון, ומנסה שוב אם סשן אחר הקדים.
push_with_sync() {
  local msg="$1" i
  for i in 1 2 3 4 5; do
    $GIT add -A
    $GIT diff --cached --quiet && { echo "  (אין שינוי לשמור)"; return 0; }
    $GIT commit -q -m "$msg" || true
    if $GIT pull --rebase --autostash -q origin main 2>/dev/null && $GIT push -q origin HEAD:main 2>/dev/null; then
      echo "  ✓ נדחף ל-main"; return 0
    fi
    echo "  ↻ סשן אחר הקדים, מסנכרן ומנסה שוב ($i/5)…"
    sleep $((i*2))
  done
  echo "  ⛔ הדחיפה נכשלה 5 פעמים. העבודה שמורה מקומית בקומיט — לדווח לבעלים."
  return 1
}
