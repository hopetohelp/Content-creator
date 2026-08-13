#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
yt_mock_api.py — שרת דמה שמחקה את YouTube Data API, לבדיקת tools/yt_comments.py
בלי מפתח אמיתי ובלי לשרוף מכסה.

למה זה קיים: בסביבת הפיתוח אין אישור גישה ליוטיוב, אבל הכלל בפרויקט הוא
שפיצ'ר לא גמור בלי תוצר שמוכיח שהוא עובד. השרת הזה מוכיח את כל מה שהוא
באמת שלנו — מעבר בין עמודים, פענוח התשובה, פורמט הפלט וטיפול בשגיאות.
מה שהוא *לא* מוכיח: שגוגל תקבל את האישור שלנו. זה נבדק בנפרד מול הרשת.

שימוש: python3 tests/yt_mock_api.py <port>
"""
import json, sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

TOTAL = 250   # מאגר תגובות מדומה, גדול מעמוד אחד כדי לבדוק דפדוף


def comment(i):
    return {
        "snippet": {
            "totalReplyCount": i % 4,
            "topLevelComment": {
                "id": f"MOCKID{i:04d}",
                "snippet": {
                    "authorDisplayName": f"צופה {i}",
                    "textDisplay": f"תגובה מספר {i} — בדיקה עם עברית ופיסוק.",
                    "likeCount": i * 2,
                    "publishedAt": "2026-08-13T10:00:00Z",
                },
            },
        }
    }


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass   # שקט — הפלט של הבדיקה צריך להישאר קריא

    def _json(self, code, body):
        raw = json.dumps(body, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        if not u.path.endswith("/commentThreads"):
            return self._json(404, {"error": {"code": 404, "message": "not found"}})

        # מחקה את דחיית גוגל כשאין מפתח וגם אין OAuth
        if "key" not in q and "Authorization" not in self.headers:
            return self._json(401, {"error": {"code": 401,
                "message": "API keys are not supported by this API.",
                "errors": [{"reason": "required"}]}})

        # תגובות מושבתות — כדי לבדוק את תרגום השגיאה לעברית
        if q.get("videoId", [""])[0] == "DISABLED":
            return self._json(403, {"error": {"code": 403, "message": "Comments disabled.",
                "errors": [{"reason": "commentsDisabled"}]}})

        n = int(q.get("maxResults", ["20"])[0])
        start = int(q.get("pageToken", ["0"])[0])
        end = min(start + n, TOTAL)
        body = {"items": [comment(i) for i in range(start, end)]}
        if end < TOTAL:
            body["nextPageToken"] = str(end)
        self._json(200, body)

    def do_POST(self):
        u = urlparse(self.path)
        if "Authorization" not in self.headers:
            return self._json(401, {"error": {"code": 401, "message": "Login Required.",
                "errors": [{"reason": "authError"}]}})
        length = int(self.headers.get("Content-Length", 0))
        payload = json.loads(self.rfile.read(length).decode()) if length else {}
        sn = payload.get("snippet", {})
        kind = "reply" if "parentId" in sn else "top"
        self._json(200, {"id": f"MOCKNEW_{kind}", "snippet": sn})


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    HTTPServer(("127.0.0.1", port), Handler).serve_forever()
