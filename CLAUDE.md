# אילוצים קשיחים
- תקציב $0. אין רכישות, אין paid API.
- אין נשים בשום פריים, רקע, מסך או פוסטר.
- שירה באנגלית. כתוביות בעברית בלבד.
- 85-95 שניות. אין placeholders. אין פריימים שחורים.
- לא לעצור לשאלות. בבלוקר — לעבור לחלופה ולתעד.
- מילים מודגשות (10%, TOKENS, BATTERY) = שכבת גרפיקה נפרדת, לא בתוך שורת כתובית עברית.

# שכבת הפקה שנבחרה
**שכבה C — נתיב פרוצדורלי מלא.** נכפתה ע"י החומרה: אין GPU בסביבה כלל
(אין `nvidia-smi`, אין `/dev/dri`, אין ROCm). 4 ליבות CPU, 15GB RAM.
שכבות A ו-B דורשות VRAM ולכן נפסלו. ComfyUI לא הותקן.

- **שוטים:** HTML/CSS → PNG דרך Chromium, ב-`tools/shot.js`.
  Chromium מותקן מראש ב-`/opt/pw-browsers` — **אין להריץ `playwright install`**.
- **תנועה:** פילטרים של ffmpeg (Ken Burns, זום, whip pan, glitch, RGB split, shake).
- **אודיו:** `tools/tts.py` (Kokoro TTS, קול) + `tools/beat.py` (ביט פרוצדורלי).

# נתיב עברית RTL
**libass מקורי + כפיית כיוון-בסיס RTL ב-U+202B (RLE) … U+202C (PDF).**
ffmpeg כאן נבנה עם `--enable-libass --enable-libfribidi --enable-libharfbuzz`,
ו-libass **כן** מיישם bidi. הכשל היחיד היה כיוון-בסיס: הוא נקבע כ-LTR, ולכן
פיסוק בקצה השורה (`.` `!` `?`) נחת בקצה הימני במקום השמאלי. העטיפה מתקנת זאת.

🔴 **אין להריץ `python-bidi` / `get_display()` על הטקסט.** נמדד: זה גורם היפוך
כפול והעברית נקראת הפוך. python-bidi מיועד לרנדרר שאין לו bidi; libass כאן אינו כזה.

**כל שורת כתובית נכתבת דרך `tools/heb_ass.py`** — הוא עוטף בכיוון RTL ומבריח
תווים אוטומטית. אין לכתוב שורות `Dialogue:` ביד.

🔴 **אין להכניס תגי עיצוב (`{\c...}`, `{\b1}`) בתוך שורת כתובית עברית** — הם
מפצלים את השורה לריצות bidi נפרדות ושוברים את סדר המילים. זו בדיוק הסיבה
שמילים מודגשות הן שכבת גרפיקה נפרדת.

# בדיקות שחייבות לעבור
```bash
python3 tools/rtl_probe.py Rubik      # מוודא שה-bidi של libass עדיין מתנהג כמצופה
bash tests/smoke.sh                   # שרשרת מקצה לקצה: וידאו+אודיו+כתובית+גרפיקה
```

# מפת הכלים
| כלי | תפקיד |
|---|---|
| `tools/heb_ass.py` | בניית קובצי ASS עם עברית תקינה (RTL כפוי + בריחת תווים) |
| `tools/rtl_probe.py` | בדיקת אמת ל-bidi בהשוואת גליפים — לא מסתמכת על קריאה בעין |
| `tools/shot.js` | HTML → PNG 1920x1080 דרך Chromium |
| `tools/beat.py` | ביט הִיפ-הופ פרוצדורלי (numpy), דטרמיניסטי, 150 BPM |
| `tools/tts.py` | Kokoro TTS מקומי, קול גברי אמריקאי, CPU בלבד |

# פונטים
ב-`fonts/` **וגם** מותקנים ברמת מערכת ב-`/usr/local/share/fonts/music-clip/`.
Rubik (עברית, כתוביות) · Noto Sans Hebrew (גיבוי) · JetBrains Mono (שכבת גרפיקה).
כולם משתנים (variable) — אין גרסאות סטטיות ב-upstream. הרישיונות ב-`fonts/licenses/`.
⚠️ אין לשים קבצים שאינם פונטים ב-`fonts/` — libass מנסה לטעון כל קובץ שם ומרעיש שגיאות.

# מבנה התיקיות
`assets/reference` רפרנסים · `assets/shots` שוטים מוגמרים · `assets/audio` אודיו ·
`subs` כתוביות · `tools` כלים · `tests` בדיקות · `output` תוצר סופי · `logs` יומנים
