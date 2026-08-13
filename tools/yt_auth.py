#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
yt_auth.py — הרשאת OAuth ליוטיוב. זה הכלי שפותח את היכולת להעלות סרטונים
ולכתוב תגובות. קריאת תגובות ציבוריות *לא* צריכה אותו (מספיק מפתח API).

למה OAuth ולא מפתח API כמו ב-Gemini:
  מפתח API מזהה *אפליקציה*, ומספיק לקריאת מידע ציבורי בלבד. כל פעולה שכותבת
  בשם הערוץ (העלאה, תגובה) דורשת הוכחה שבעל הערוץ אישר אותה — וזה OAuth.

התהליך (חד-פעמי, כמה דקות):
  1. באתר console.cloud.google.com → "APIs & Services" → "Library" →
     להפעיל "YouTube Data API v3".
  2. "Credentials" → "Create Credentials" → "OAuth client ID" →
     סוג האפליקציה: "Desktop app". מקבלים Client ID ו-Client Secret.
  3. במסך "OAuth consent screen" להוסיף את חשבון הגוגל של הערוץ תחת
     "Test users", ולפרסם ל-"In production" (אחרת הטוקן פג כל 7 ימים).
  4. להגדיר בסביבה: YT_CLIENT_ID ו-YT_CLIENT_SECRET.
  5. python3 tools/yt_auth.py --auth-url      → לפתוח את הקישור בדפדפן, לאשר.
     הדפדפן ינסה לעבור ל-localhost וייכשל — זה תקין. מעתיקים מ*שורת הכתובת*
     את הערך שאחרי code= (עד ה-& הראשון אם יש).
  6. python3 tools/yt_auth.py --exchange "<הקוד>"  → מקבלים refresh token.
  7. לשמור אותו בסביבה כ-YT_REFRESH_TOKEN. מכאן זה עובד לבד.

הערה על אבטחה: refresh token = מפתח לערוץ. לא לשמור בקוד ולא בריפו,
רק במשתני סביבה (בהגדרות הסביבה ב-claude.ai/code).

שימוש שוטף (הכלים האחרים קוראים לזה לבד):
  python3 tools/yt_auth.py --token     → מדפיס access token תקף לשעה
"""
import argparse, json, os, sys, urllib.parse, urllib.request, urllib.error

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
REDIRECT = "http://localhost:8080"   # לקוח מסוג Desktop — לולאה מקומית

# upload = העלאת סרטונים. force-ssl = קריאה/כתיבה של תגובות וניהול סרטונים.
SCOPES = ["https://www.googleapis.com/auth/youtube.upload",
          "https://www.googleapis.com/auth/youtube.force-ssl"]


def _env(name, hint):
    v = os.environ.get(name, "").strip()
    if not v:
        sys.exit(f"שגיאה: משתנה הסביבה {name} לא מוגדר.\n  {hint}")
    return v


def _post(url, data):
    """POST עם גוף form-encoded. מחזיר dict, או עוצר עם שגיאה קריאה."""
    body = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(url, data=body,
                                 headers={"Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        raw = e.read().decode(errors="replace")
        try:
            err = json.loads(raw)
            msg = err.get("error_description") or err.get("error") or raw
        except json.JSONDecodeError:
            msg = raw
        sys.exit(f"שגיאת גוגל ({e.code}): {msg}")
    except urllib.error.URLError as e:
        sys.exit(f"שגיאת רשת: {e.reason}")


def auth_url():
    """בונה את קישור האישור שהבעלים פותח בדפדפן שלו."""
    params = {
        "client_id": _env("YT_CLIENT_ID", "ראו את ההסבר בראש הקובץ, שלב 2."),
        "redirect_uri": REDIRECT,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "access_type": "offline",   # בלי זה לא מקבלים refresh token
        "prompt": "consent",        # מכריח הנפקה מחדש גם אם כבר אושר בעבר
    }
    return f"{AUTH_URL}?{urllib.parse.urlencode(params)}"


def exchange(code):
    """ממיר את הקוד החד-פעמי מהדפדפן ל-refresh token קבוע."""
    d = _post(TOKEN_URL, {
        "client_id": _env("YT_CLIENT_ID", "ראו שלב 2."),
        "client_secret": _env("YT_CLIENT_SECRET", "ראו שלב 2."),
        "code": code.strip(),
        "grant_type": "authorization_code",
        "redirect_uri": REDIRECT,
    })
    if "refresh_token" not in d:
        sys.exit("גוגל לא החזירה refresh token. סיבה נפוצה: הקוד כבר נוצל פעם אחת.\n"
                 "להריץ שוב --auth-url ולקחת קוד חדש.")
    return d["refresh_token"]


def access_token():
    """מחליף refresh token ב-access token תקף לשעה. זו הקריאה השוטפת."""
    d = _post(TOKEN_URL, {
        "client_id": _env("YT_CLIENT_ID", "ראו שלב 2."),
        "client_secret": _env("YT_CLIENT_SECRET", "ראו שלב 2."),
        "refresh_token": _env("YT_REFRESH_TOKEN", "להריץ --auth-url ואז --exchange."),
        "grant_type": "refresh_token",
    })
    return d["access_token"]


def main():
    p = argparse.ArgumentParser(description="הרשאת OAuth ליוטיוב")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--auth-url", action="store_true", help="הדפס קישור אישור לדפדפן")
    g.add_argument("--exchange", metavar="CODE", help="המר קוד מהדפדפן ל-refresh token")
    g.add_argument("--token", action="store_true", help="הדפס access token תקף")
    a = p.parse_args()

    if a.auth_url:
        print("פתחו את הקישור בדפדפן, אשרו, והעתיקו את הערך שאחרי code= משורת הכתובת:\n")
        print(auth_url())
    elif a.exchange:
        print("שמרו את זה כמשתנה סביבה YT_REFRESH_TOKEN:\n")
        print(exchange(a.exchange))
    else:
        print(access_token())


if __name__ == "__main__":
    main()
