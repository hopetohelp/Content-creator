#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
yt_upload.py — העלאת סרטון ליוטיוב דרך ה-API. דורש הרשאת OAuth (tools/yt_auth.py).

🔴 חסם שחייבים להכיר לפני שמשתמשים בכלי הזה:
  כל סרטון שמועלה דרך ה-API מפרויקט שלא עבר ביקורת תאימות של יוטיוב
  ננעל אוטומטית כ"פרטי" — ולפי דף העזרה הרשמי של יוטיוב, על נעילה כזאת
  *אין אפשרות ערעור* ואי אפשר לשחרר אותה ידנית. הסרטון תקוע פרטי לתמיד.
  הדרך היחידה לשחרר: לעבור ביקורת (טופס yt_api_form), או להעלות ידנית
  דרך יוטיוב סטודיו. ראו: מסמכים/4. יוטיוב — מחקר, כלים ותהליך הרשאה.md

  לכן ברירת המחדל כאן היא --privacy private, והכלי דורש --i-know-the-risk
  כדי לרוץ בפועל. זו לא בירוקרטיה — זו הגנה מפני שריפת סרטון מוגמר.

מכסה: מאז 1.6.2026 להעלאה יש מכסה נפרדת של 100 העלאות ביום. לא צוואר בקבוק.

שימוש:
  # בדיקה יבשה — מוודא שהקובץ והמטא-דאטה תקינים, בלי לגעת ברשת
  python3 tools/yt_upload.py --file output/clip.mp4 --title "..." --dry-run

  # העלאה אמיתית
  python3 tools/yt_upload.py --file output/clip.mp4 \
      --title "כותרת" --description "תיאור" --tags "ai,music" --i-know-the-risk
"""
import argparse, json, os, sys, urllib.parse, urllib.request, urllib.error

UPLOAD = "https://www.googleapis.com/upload/youtube/v3/videos"
CHUNK = 1024 * 1024 * 4   # 4MB — רלוונטי רק לדיווח התקדמות


def _token():
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import yt_auth
    return yt_auth.access_token()


def _fail(e):
    raw = e.read().decode(errors="replace")
    try:
        err = json.loads(raw).get("error", {})
        msg = err.get("message", raw)
        reason = (err.get("errors") or [{}])[0].get("reason", "")
    except json.JSONDecodeError:
        msg, reason = raw, ""
    hints = {
        "quotaExceeded": "נגמרו 100 ההעלאות היומיות. מתאפס בחצות שעון האוקיינוס השקט.",
        "uploadLimitExceeded": "הערוץ הגיע למגבלת העלאות. להמתין ולנסות מחר.",
        "forbidden": "אין הרשאה. לוודא שה-OAuth כולל את ההיתר youtube.upload.",
        "youtubeSignupRequired": "לחשבון הגוגל הזה עדיין אין ערוץ יוטיוב. לפתוח ידנית באתר.",
    }
    tip = hints.get(reason, "")
    sys.exit(f"שגיאת יוטיוב ({e.code}{'/' + reason if reason else ''}): {msg}"
             + (f"\n→ {tip}" if tip else ""))


def build_metadata(a):
    """בונה את גוף המטא-דאטה. selfDeclaredMadeForKids חובה מצד יוטיוב."""
    return {
        "snippet": {
            "title": a.title,
            "description": a.description or "",
            "tags": [t.strip() for t in (a.tags or "").split(",") if t.strip()],
            "categoryId": a.category,
        },
        "status": {
            "privacyStatus": a.privacy,
            "selfDeclaredMadeForKids": a.made_for_kids,
        },
    }


def start_session(meta, size, token):
    """שלב 1: פותח הפעלת העלאה. מחזיר את הכתובת שאליה שולחים את הבייטים."""
    url = f"{UPLOAD}?{urllib.parse.urlencode({'uploadType': 'resumable', 'part': 'snippet,status'})}"
    req = urllib.request.Request(url, data=json.dumps(meta).encode(), headers={
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "X-Upload-Content-Length": str(size),
        "X-Upload-Content-Type": "video/*",
    })
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            loc = r.headers.get("Location")
            if not loc:
                sys.exit("יוטיוב לא החזירה כתובת העלאה. לנסות שוב.")
            return loc
    except urllib.error.HTTPError as e:
        _fail(e)
    except urllib.error.URLError as e:
        sys.exit(f"שגיאת רשת: {e.reason}")


def send_bytes(session_url, path, size, token):
    """שלב 2: שולח את הקובץ עצמו ומחזיר את פרטי הסרטון שנוצר."""
    with open(path, "rb") as f:
        req = urllib.request.Request(session_url, data=f, method="PUT", headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "video/*",
            "Content-Length": str(size),
        })
        try:
            with urllib.request.urlopen(req, timeout=1800) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            _fail(e)
        except urllib.error.URLError as e:
            sys.exit(f"שגיאת רשת בזמן ההעלאה: {e.reason}")


def main():
    p = argparse.ArgumentParser(description="העלאת סרטון ליוטיוב")
    p.add_argument("--file", required=True, help="נתיב לקובץ הווידאו")
    p.add_argument("--title", required=True, help="כותרת (עד 100 תווים)")
    p.add_argument("--description", default="", help="תיאור (עד 5000 תווים)")
    p.add_argument("--tags", default="", help="תגיות מופרדות בפסיק")
    p.add_argument("--category", default="10", help="קטגוריה (10 = Music)")
    p.add_argument("--privacy", choices=["private", "unlisted", "public"], default="private")
    p.add_argument("--made-for-kids", action="store_true", help="תוכן המיועד לילדים")
    p.add_argument("--dry-run", action="store_true", help="בדיקת תקינות בלי רשת")
    p.add_argument("--i-know-the-risk", action="store_true",
                   help="אישור שקראתם על נעילת הסרטון כפרטי")
    a = p.parse_args()

    if not os.path.isfile(a.file):
        sys.exit(f"לא נמצא קובץ: {a.file}")
    size = os.path.getsize(a.file)
    if size == 0:
        sys.exit(f"הקובץ ריק (0 בייטים): {a.file}")
    if len(a.title) > 100:
        sys.exit(f"הכותרת ארוכה מדי: {len(a.title)} תווים, המקסימום 100.")
    if len(a.description) > 5000:
        sys.exit(f"התיאור ארוך מדי: {len(a.description)} תווים, המקסימום 5000.")

    meta = build_metadata(a)
    mb = size / 1024 / 1024

    if a.dry_run:
        print("בדיקה יבשה — לא נשלח כלום לרשת.")
        print(f"קובץ: {a.file} ({mb:.1f} MB)")
        print(json.dumps(meta, ensure_ascii=False, indent=2))
        print("\nתקין. להעלאה אמיתית: להסיר --dry-run ולהוסיף --i-know-the-risk")
        return

    if not a.i_know_the_risk:
        sys.exit("עצירה מכוונת: העלאה דרך ה-API עלולה לנעול את הסרטון כפרטי לצמיתות.\n"
                 "לקרוא את ההסבר בראש הקובץ, ואז להוסיף --i-know-the-risk.\n"
                 "החלופה הבטוחה: להעלות ידנית דרך יוטיוב סטודיו.")

    token = _token()
    print(f"פותח הפעלת העלאה ({mb:.1f} MB)...")
    session = start_session(meta, size, token)
    print("מעלה את הקובץ. בקובץ גדול זה יכול לקחת כמה דקות...")
    r = send_bytes(session, a.file, size, token)

    vid = r.get("id", "")
    status = r.get("status", {}).get("privacyStatus", "?")
    print(f"\nהועלה. מזהה: {vid}")
    print(f"קישור: https://www.youtube.com/watch?v={vid}")
    print(f"מצב פרטיות: {status}")
    if status == "private" and a.privacy != "private":
        print("\n⚠️ ביקשתם פרסום אבל יוטיוב נעלה את הסרטון כפרטי — "
              "זה הסימן שהפרויקט לא עבר ביקורת תאימות. לא ניתן לשחרר ידנית.")


if __name__ == "__main__":
    main()
