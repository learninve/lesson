// Renders every Hebrew overlay layer to a transparent PNG with headless Chromium,
// so RTL ordering, Heebo and colour emoji are handled by a real text engine.
//   node render_overlays.cjs <layers.json> <assets_dir> <out_dir>
// Writes <out_dir>/<id>.png and <out_dir>/manifest.json ({id: {file, x, y, w, h}}).
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

const [layersPath, assetsDir, outDir] = process.argv.slice(2).map((p) => path.resolve(p));
const cfg = JSON.parse(fs.readFileSync(layersPath, 'utf8'));
fs.mkdirSync(outDir, { recursive: true });

const W = cfg.frame.w;
const esc = (s) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;');
// '*word*' -> gold highlight ; '@@line@@' -> big brand line
const fmt = (line) => {
  if (line.startsWith('@@') && line.endsWith('@@')) {
    return `<span class="brandline">${esc(line.slice(2, -2))}</span>`;
  }
  // emoji runs are wrapped in an LTR isolate so '😭💧' keeps the same left-to-right order as the English original
  return esc(line)
    .replace(/\*([^*]+)\*/g, '<span class="k">$1</span>')
    .replace(/((?:\p{Extended_Pictographic}\uFE0F?)+)/gu, '<span dir="ltr" style="unicode-bidi:isolate">$1</span>');
};

const fontFace = (weight) => `
@font-face{font-family:Heebo;font-weight:${weight};src:url(fonts/heebo-hebrew-${weight}-normal.woff2) format('woff2');
  unicode-range:U+0590-05FF,U+200C-2010,U+20AA,U+25CC,U+FB1D-FB4F;}
@font-face{font-family:Heebo;font-weight:${weight};src:url(fonts/heebo-latin-${weight}-normal.woff2) format('woff2');
  unicode-range:U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+2000-206F,U+2074,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD;}`;

const tb = cfg.text_box;
const ec = cfg.end_card;
const bannerH = cfg.banner.solid_h + cfg.banner.shadow_h;

const textLayerHtml = cfg.text_layers
  .map(
    (l) => `<div class="layer tl" id="${l.id}" data-size="${l.size}" style="top:${tb.top}px;height:${tb.height}px">
  ${l.lines.map((ln) => `<div class="ln">${fmt(ln)}</div>`).join('\n  ')}
</div>`
  )
  .join('\n');

const html = `<!doctype html><html lang="he" dir="rtl"><head><meta charset="utf-8"><style>
${fontFace(800)}${fontFace(900)}
:root{--green:#3F441C;--green-hi:#4B5224;--gold:#E2BA4E;--gold-hi:#FFD95A;--cream:#F7EEDA;}
html,body{margin:0;padding:0;background:transparent;width:${W}px;height:${cfg.frame.h}px;overflow:hidden}
body{font-family:Heebo,'Noto Color Emoji',sans-serif;font-weight:900;color:var(--cream)}
.layer{position:absolute;left:0;width:${W}px;display:none}
body[data-show="banner"] #banner,
body[data-show="scrim"] #scrim,
body[data-show="endcard"] #endcard{display:block}
${cfg.text_layers.map((l) => `body[data-show="${l.id}"] #${l.id}`).join(',\n')}{display:flex}

/* opaque banner: covers the burned-in English caption (rows y~110..290 of 1280 => ~165..435 px at 1080x1920) */
#banner{top:0;height:${bannerH}px;
  background:
    linear-gradient(to bottom,var(--green-hi) 0,var(--green) 55%,#363B17 ${cfg.banner.solid_h - 8}px,
    #363B17 ${cfg.banner.solid_h - 8}px,#363B17 ${cfg.banner.solid_h}px,rgba(0,0,0,.55) ${cfg.banner.solid_h}px,rgba(0,0,0,0) ${bannerH}px);}
#banner .gold{position:absolute;left:0;right:0;top:${cfg.banner.solid_h - 14}px;height:6px;background:linear-gradient(to left,#b98f2c,var(--gold-hi),#b98f2c)}
#banner .gold2{position:absolute;left:0;right:0;top:${cfg.banner.solid_h - 26}px;height:2px;background:rgba(226,186,78,.55)}

.tl{flex-direction:column;align-items:center;justify-content:center;text-align:center;direction:rtl}
.ln{white-space:nowrap;line-height:1.14;font-weight:900;color:var(--cream);
  -webkit-text-stroke:9px rgba(0,0,0,.9);paint-order:stroke fill;
  text-shadow:0 5px 0 rgba(0,0,0,.45)}
.k{color:var(--gold-hi)}
.brandline{display:inline-block;color:var(--gold-hi);font-size:1.5em;letter-spacing:.01em}
.ln img,.ln .emo{vertical-align:-.08em}

#scrim{top:${ec.scrim.top}px;height:${ec.scrim.height}px;
  background:linear-gradient(to bottom,rgba(16,20,8,0) 0,rgba(16,20,8,.58) 22%,rgba(16,20,8,.70) 100%)}
#endcard{top:${ec.content.top}px;height:${ec.content.height}px;display:none;flex-direction:column;align-items:center;justify-content:flex-start}
body[data-show="endcard"] #endcard{display:flex}
#endcard img{width:${ec.logo_px}px;height:${ec.logo_px}px;filter:drop-shadow(0 10px 22px rgba(0,0,0,.65))}
#endcard .lbl{margin-top:22px;font-size:60px;font-weight:800;color:var(--cream);-webkit-text-stroke:8px rgba(0,0,0,.85);paint-order:stroke fill;text-shadow:0 4px 0 rgba(0,0,0,.4)}
#endcard .pill{margin-top:14px;padding:6px 56px 10px;border-radius:90px;background:rgba(12,15,6,.78);border:5px solid var(--gold);
  box-shadow:0 8px 30px rgba(0,0,0,.55)}
#endcard .ph{direction:ltr;unicode-bidi:isolate;font-size:112px;font-weight:900;color:var(--gold-hi);letter-spacing:.02em;line-height:1.15;
  -webkit-text-stroke:7px rgba(0,0,0,.85);paint-order:stroke fill}
</style></head><body>
<div class="layer" id="banner"><div class="gold2"></div><div class="gold"></div></div>
${textLayerHtml}
<div class="layer" id="scrim"></div>
<div class="layer" id="endcard">
  <img src="logo.png" alt="">
  <div class="lbl">${esc(ec.label)}</div>
  <div class="pill"><div class="ph">${esc(ec.phone)}</div></div>
</div>
</body></html>`;

(async () => {
  fs.writeFileSync(path.join(assetsDir, '_overlays.html'), html);
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: W, height: cfg.frame.h }, deviceScaleFactor: 1 });
  await page.goto('file://' + path.join(assetsDir, '_overlays.html'));
  await page.evaluate(() => document.fonts.ready);

  // auto-fit: shrink a text layer's font until its widest line fits inside the 1080px frame with margins
  const MAXW = 940;
  const manifest = {};
  const shoot = async (id, el_id) => {
    await page.evaluate((i) => (document.body.dataset.show = i), id);
    const el = await page.$('#' + el_id);
    const file = path.join(outDir, id + '.png');
    const box = await el.boundingBox();
    await el.screenshot({ path: file, omitBackground: true });
    manifest[id] = { file: path.basename(file), x: Math.round(box.x), y: Math.round(box.y), w: Math.round(box.width), h: Math.round(box.height) };
  };

  for (const l of cfg.text_layers) {
    await page.evaluate((i) => (document.body.dataset.show = i), l.id);
    const fit = await page.evaluate(
      ({ id, max }) => {
        const el = document.getElementById(id);
        let size = parseFloat(el.dataset.size);
        const apply = () => el.querySelectorAll('.ln').forEach((n) => (n.style.fontSize = size + 'px'));
        const widest = () => Math.max(...[...el.querySelectorAll('.ln')].map((n) => n.getBoundingClientRect().width));
        const tall = () => el.scrollHeight > el.clientHeight + 2;
        apply();
        while ((widest() > max || tall()) && size > 30) { size -= 2; apply(); }
        return { size, widest: widest() };
      },
      { id: l.id, max: MAXW }
    );
    console.log(`layer ${l.id}: font ${fit.size}px, widest line ${Math.round(fit.widest)}px`);
    await shoot(l.id, l.id);
  }
  await shoot('banner', 'banner');
  await shoot('scrim', 'scrim');
  await shoot('endcard', 'endcard');
  fs.writeFileSync(path.join(outDir, 'manifest.json'), JSON.stringify(manifest, null, 2));
  await browser.close();
  console.log('wrote', Object.keys(manifest).join(', '));
})();
