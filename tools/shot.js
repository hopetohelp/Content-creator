#!/usr/bin/env node
/**
 * shot.js — מצלם עמוד HTML לתמונת PNG ב-1920x1080 דרך Chromium.
 * זה מנוע השוטים של שכבה C: מסכי טרמינל/IDE/טלפון/התראות נבנים כ-HTML+CSS
 * ומצולמים. דטרמיניסטי לגמרי, בלי GPU, בלי מודלים, בלי רשת.
 *
 * שימוש:  node tools/shot.js <קלט.html> <פלט.png> [רוחב] [גובה] [deviceScaleFactor] [--transparent]
 *
 * --transparent : מצלם עם ערוץ אלפא (רקע שקוף) — לשכבות גרפיקה שמורכבות מעל וידאו.
 */
const { chromium } = require('/opt/node22/lib/node_modules/playwright');
const path = require('path');

(async () => {
  const argv = process.argv.filter(a => a !== '--transparent');
  const transparent = process.argv.includes('--transparent');
  const [, , src, out, w = '1920', h = '1080', dsf = '1'] = argv;
  if (!src || !out) {
    console.error('שימוש: node tools/shot.js <קלט.html> <פלט.png> [רוחב] [גובה] [scale]');
    process.exit(2);
  }
  const browser = await chromium.launch({
    args: ['--no-sandbox', '--disable-dev-shm-usage', '--force-color-profile=srgb',
           '--font-render-hinting=none', '--disable-lcd-text'],
  });
  const page = await browser.newPage({
    viewport: { width: +w, height: +h },
    deviceScaleFactor: +dsf,
  });
  await page.goto('file://' + path.resolve(src), { waitUntil: 'networkidle' });
  await page.evaluate(() => document.fonts.ready);   // ודא שהפונטים נטענו לפני הצילום
  await page.screenshot({ path: out, type: 'png', omitBackground: transparent });
  await browser.close();
  console.log(`נוצר: ${out}  (${w}x${h} @${dsf}x${transparent ? ', שקוף' : ''})`);
})().catch(e => { console.error('שגיאה:', e.message); process.exit(1); });
