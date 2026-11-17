// Reels/TikTok cover 1080x1920. Key content stays inside the central 3:4 grid crop (y 240..1680).
//   node make_cover.cjs <graded_frame.png> <out.png>
const fs = require('fs'), path = require('path');
const { chromium } = require('playwright');
const [frame, out] = process.argv.slice(2).map((p) => path.resolve(p));
const A = path.join(__dirname, 'assets');
const ff = (w) => `@font-face{font-family:Heebo;font-weight:${w};src:url(fonts/heebo-hebrew-${w}-normal.woff2);unicode-range:U+0590-05FF,U+200C-2010,U+20AA,U+FB1D-FB4F}
@font-face{font-family:Heebo;font-weight:${w};src:url(fonts/heebo-latin-${w}-normal.woff2);unicode-range:U+0000-00FF,U+2000-206F}`;
const html = `<!doctype html><html lang="he" dir="rtl"><meta charset="utf-8"><style>${ff(800)}${ff(900)}
body{margin:0;width:1080px;height:1920px;position:relative;overflow:hidden;font-family:Heebo,'Noto Color Emoji',sans-serif;font-weight:900;background:#222}
.bg{position:absolute;inset:0;background:url(${frame}) center/cover}
.banner{position:absolute;top:0;left:0;right:0;height:560px;background:linear-gradient(#4B5224,#3F441C 55%,#363B17)}
.gold{position:absolute;left:0;right:0;top:546px;height:8px;background:linear-gradient(to left,#b98f2c,#FFD95A,#b98f2c)}
.sh{position:absolute;top:560px;left:0;right:0;height:60px;background:linear-gradient(rgba(0,0,0,.55),transparent)}
.t{position:absolute;top:300px;left:0;right:0;text-align:center;color:#F7EEDA;font-size:104px;line-height:1.1;
  -webkit-text-stroke:11px rgba(0,0,0,.9);paint-order:stroke fill;text-shadow:0 6px 0 rgba(0,0,0,.45)}
.k{color:#FFD95A}
.low{position:absolute;left:0;right:0;top:1180px;height:740px;background:linear-gradient(rgba(16,20,8,0),rgba(16,20,8,.72) 30%,rgba(16,20,8,.8))}
.logo{position:absolute;top:1290px;left:50%;margin-left:-170px;width:340px;filter:drop-shadow(0 10px 22px rgba(0,0,0,.65))}
.pill{position:absolute;top:1650px;left:50%;transform:translateX(-50%);padding:4px 44px 8px;border-radius:80px;background:rgba(12,15,6,.8);border:5px solid #E2BA4E;
  color:#FFD95A;font-size:84px;direction:ltr;unicode-bidi:isolate;white-space:nowrap}
.tag{position:absolute;top:1170px;right:60px;background:#FFD95A;color:#1b1f0c;font-size:56px;padding:6px 34px 12px;border-radius:16px;transform:rotate(-4deg);box-shadow:0 6px 0 rgba(0,0,0,.5)}
</style><body><div class="bg"></div><div class="banner"></div><div class="gold"></div><div class="sh"></div>
<div class="t">זה מה שהיה <span class="k">מוסתר</span><br>בתוך המושב <span dir="ltr" style="unicode-bidi:isolate">😭💧</span></div>
<div class="low"></div><div class="tag">התוצאה מדברת</div>
<img class="logo" src="logo.png"><div class="pill">055-7718519</div></body></html>`;
(async () => {
  const f = path.join(A, '_cover.html'); fs.writeFileSync(f, html);
  const b = await chromium.launch(); const p = await b.newPage({ viewport: { width: 1080, height: 1920 } });
  await p.goto('file://' + f); await p.evaluate(() => document.fonts.ready);
  await p.waitForTimeout(300); await p.screenshot({ path: out }); await b.close(); console.log('wrote', out);
})();
