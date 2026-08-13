#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
yt_comments.py — קריאה וכתיבה של תגובות ביוטיוב.

קריאה של תגובות ציבוריות דורשת רק מפתח API (YOUTUBE_API_KEY).
כתיבת תגובה או תשובה דורשת הרשאת OAuth — ראו tools/yt_auth.py.

עלות מכסה (מתוך 10,000 יחידות ביום, מתאפסות בחצות שעון האוקיינוס השקט):
  קריאת עמוד תגובות = 1 יחידה   → בפועל בלי הגבלה
  כתיבת תגובה/תשובה = 50 יחידות → כ-200 ביום

שימוש:
  # קריאה (רק מפתח API)
  python3 tools/yt_comments.py --video VIDEO_ID
  python3 tools/yt_comments.py --video VIDEO_ID --max 100 --order relevance --json

  # כתיבה (דורש OAuth)
  python3 tools/yt_comments.py --video VIDEO_ID --post "תגובה חדשה"
  python3 tools/yt_comments.py --reply-to COMMENT_ID --post "תשובה לתגובה"

אזהרה: מסנן הספאם של יוטיוב עלול לסמן תגובות אוטומטיות, במיוחד בערוץ חדש.
התגובה תיראה לכם תקינה אבל תוסתר מאחרים. לכתוב במידה ובאופן אנושי.
"""
import argparse, json, os, sys, urllib.parse, urllib.request, urllib.error

API = "https://www.googleapis.com/youtube/v3"


def _request(url, token=None, payload=None):
    """קריאה ל-API. עם payload → POST. מחזיר dict, או עוצר עם שגיאה בעברית."""
    data, headers = None, {}
    if payload is not None:
        data = json.dumps(payload).encode()
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        _explain(e)
    except urllib.error.URLError as e:
        sys.exit(f"שגיאת רשת: {e.reason}")


def _explain(e):
    """מתרגם שגיאות נפוצות של יוטיוב להסבר מעשי בעברית."""
    raw = e.read().decode(errors="replace")
    try:
        err = json.loads(raw).get("error", {})
        msg = err.get("message", raw)
        reason = (err.get("errors") or [{}])[0].get("reason", "")
    except json.JSONDecodeError:
        msg, reason = raw, ""

    hints = {
        "quotaExceeded": "המכסה היומית נגמרה. היא מתאפסת בחצות שעון האוקיינוס השקט.",
        "commentsDisabled": "התגובות מושבתות בסרטון הזה.",
        "videoNotFound": "לא נמצא סרטון עם המזהה הזה.",
        "forbidden": "אין הרשאה לפעולה הזאת עם האישור הנוכחי.",
        "insufficientPermissions": "ל-OAuth חסר ההיתר youtube.force-ssl. להריץ שוב את yt_auth.py.",
        "authError": "האישור פג. להריץ שוב: python3 tools/yt_auth.py --token",
    }
    tip = hints.get(reason, "")
    if e.code == 401 and "API keys are not supported" in msg:
        tip = ("YouTube Data API v3 כנראה לא מופעל בפרויקט של המפתח, "
               "או שהמפתח מוגבל ל-API אחר. להפעיל ב-console.cloud.google.com → Library.")
    sys.exit(f"שגיאת יוטיוב ({e.code}{'/' + reason if reason else ''}): {msg}"
             + (f"\n→ {tip}" if tip else ""))


def _token():
    """access token דרך yt_auth.py. נדרש לכל כתיבה."""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import yt_auth
    return yt_auth.access_token()


def read(video_id, want, order, api_base, key=None, token=None):
    """מושך תגובות עליונות. עובר בין עמודים עד שהגיע ל-want או שנגמרו."""
    out, page = [], None
    while len(out) < want:
        q = {"part": "snippet", "videoId": video_id, "order": order,
             "maxResults": min(100, want - len(out))}
        if key:
            q["key"] = key
        if page:
            q["pageToken"] = page
        d = _request(f"{api_base}/commentThreads?{urllib.parse.urlencode(q)}", token=token)
        for item in d.get("items", []):
            s = item["snippet"]["topLevelComment"]["snippet"]
            out.append({
                "id": item["snippet"]["topLevelComment"]["id"],
                "author": s.get("authorDisplayName", ""),
                "text": s.get("textDisplay", ""),
                "likes": s.get("likeCount", 0),
                "published": s.get("publishedAt", ""),
                "replies": item["snippet"].get("totalReplyCount", 0),
            })
        page = d.get("nextPageToken")
        if not page:
            break
    return out[:want]


def post(text, api_base, video_id=None, parent_id=None):
    """כותב תגובה עליונה (video_id) או תשובה לתגובה קיימת (parent_id)."""
    token = _token()
    if parent_id:
        url = f"{api_base}/comments?part=snippet"
        body = {"snippet": {"parentId": parent_id, "textOriginal": text}}
    else:
        url = f"{api_base}/commentThreads?part=snippet"
        body = {"snippet": {"videoId": video_id,
                            "topLevelComment": {"snippet": {"textOriginal": text}}}}
    return _request(url, token=token, payload=body)


def main():
    p = argparse.ArgumentParser(description="תגובות יוטיוב — קריאה וכתיבה")
    p.add_argument("--video", help="מזהה הסרטון (11 תווים מתוך הקישור)")
    p.add_argument("--reply-to", metavar="COMMENT_ID", help="מזהה תגובה שעונים לה")
    p.add_argument("--post", metavar="TEXT", help="טקסט לכתיבה (דורש OAuth)")
    p.add_argument("--max", type=int, default=20, help="כמה תגובות למשוך (ברירת מחדל 20)")
    p.add_argument("--order", choices=["time", "relevance"], default="relevance")
    p.add_argument("--json", action="store_true", help="פלט JSON במקום טקסט")
    p.add_argument("--out", help="שמור את הפלט לקובץ")
    p.add_argument("--api-base", default=API, help="עקיפת כתובת ה-API (לבדיקות בלבד)")
    a = p.parse_args()

    if a.post:
        if not (a.video or a.reply_to):
            sys.exit("לכתיבה צריך --video (תגובה חדשה) או --reply-to (תשובה).")
        r = post(a.post, a.api_base, video_id=a.video, parent_id=a.reply_to)
        cid = r.get("id", "")
        print(f"נכתב בהצלחה. מזהה התגובה: {cid}")
        print("שימו לב: אם מסנן הספאם סימן אותה, היא תיראה לכם אבל לא לאחרים.")
        return

    if not a.video:
        sys.exit("צריך --video עם מזהה סרטון. לעזרה: --help")

    key = os.environ.get("YOUTUBE_API_KEY", "").strip()
    token = None
    if not key:
        # בלי מפתח API אפשר לקרוא גם עם OAuth, אם הוא כבר מוגדר.
        if os.environ.get("YT_REFRESH_TOKEN"):
            token = _token()
        else:
            sys.exit("לקריאה צריך YOUTUBE_API_KEY (או הרשאת OAuth מוגדרת).\n"
                     "→ להפעיל YouTube Data API v3 ב-console.cloud.google.com "
                     "וליצור מפתח תחת Credentials.")

    items = read(a.video, a.max, a.order, a.api_base, key=key, token=token)

    if a.json:
        text = json.dumps(items, ensure_ascii=False, indent=2)
    else:
        lines = [f"נמצאו {len(items)} תגובות בסרטון {a.video}:", ""]
        for c in items:
            lines.append(f"[{c['likes']} לייקים · {c['replies']} תשובות] {c['author']}")
            lines.append(f"  {c['text']}")
            lines.append(f"  ({c['published']} · id={c['id']})")
            lines.append("")
        text = "\n".join(lines)

    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"נשמר: {a.out} ({len(items)} תגובות)")
    else:
        print(text)


if __name__ == "__main__":
    main()
