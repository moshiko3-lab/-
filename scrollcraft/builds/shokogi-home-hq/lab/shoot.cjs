const { chromium } = require('/opt/node22/lib/node_modules/playwright');
const path = require('path');
const fs = require('fs');

const URL = 'file://' + path.resolve(__dirname, 'index.html');
const EXEC = '/opt/pw-browsers/chromium-1194/chrome-linux/chrome';

(async () => {
  const mode = process.argv[2] || 'desk';
  const mobile = mode === 'mob';
  const W = mobile ? 390 : 1440, H = mobile ? 844 : 900;
  const outDir = path.join(__dirname, mobile ? 'mob' : 'desk');
  fs.mkdirSync(outDir, { recursive: true });

  const browser = await chromium.launch({ executablePath: EXEC });
  const page = await browser.newPage({ viewport: { width: W, height: H }, deviceScaleFactor: 1 });
  await page.goto(URL, { waitUntil: 'networkidle' });
  await page.waitForTimeout(500);

  const total = await page.evaluate(() => document.documentElement.scrollHeight);
  // find the two pinned acts
  const acts = await page.evaluate(() => {
    const g = s => { const e = document.querySelector(s); if(!e) return null; const r = e.getBoundingClientRect(); return { top: r.top + scrollY, h: e.offsetHeight }; };
    return { ways: g('.ways'), peak: g('.peak') };
  });

  const shots = [];
  // even sweep
  const N = mobile ? 10 : 12;
  for (let i = 0; i <= N; i++) shots.push({ name: `sweep-${String(i).padStart(2,'0')}`, y: Math.round((total - H) * i / N) });
  // targeted sub-positions inside the pinned acts
  if (acts.ways) for (const f of [0.08, 0.5, 0.92]) shots.push({ name: `ways-${f}`, y: Math.round(acts.ways.top + (acts.ways.h - H) * f) });
  if (acts.peak) for (const f of [0.05, 0.45, 0.8]) shots.push({ name: `peak-${f}`, y: Math.round(acts.peak.top + (acts.peak.h - H) * f) });

  for (const s of shots) {
    await page.evaluate(y => window.scrollTo(0, y), s.y);
    await page.waitForTimeout(650);
    await page.screenshot({ path: path.join(outDir, s.name + '.png') });
  }
  console.log('total scrollHeight', total, 'shots', shots.length, '->', outDir);
  await browser.close();
})();
