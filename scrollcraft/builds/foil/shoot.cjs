const { chromium } = require('/opt/node22/lib/node_modules/playwright');
const path = require('path');
(async () => {
  const b = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium-1194/chrome-linux/chrome' });
  const base = 'file://' + path.resolve(__dirname, 'foil-lab.html');
  for (const mode of ['before', 'after']) {
    const p = await b.newPage({ viewport: { width: 1280, height: 900 }, deviceScaleFactor: 1 });
    await p.goto(base + (mode === 'after' ? '?after' : ''), { waitUntil: 'networkidle' });
    await p.waitForTimeout(600);
    await p.screenshot({ path: mode + '-full.png', fullPage: true });
    // also a hero+facts crop for a clean side-by-side
    await p.setViewportSize({ width: 1280, height: 1600 });
    await p.evaluate(() => window.scrollTo(0,0));
    await p.waitForTimeout(300);
    await p.screenshot({ path: mode + '-top.png' });
    await p.close();
  }
  console.log('done');
  await b.close();
})();
