const { chromium } = require('/opt/node22/lib/node_modules/playwright');
const path = require('path');
(async () => {
  const b = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium-1194/chrome-linux/chrome' });
  const p = await b.newPage({ viewport: { width: 1280, height: 900 }, deviceScaleFactor: 1 });
  await p.goto('file://' + path.resolve(__dirname, 'foil-lab.html'), { waitUntil: 'networkidle' });
  await p.waitForTimeout(700);
  // fleet section crop
  const fleet = await p.$('.fleet');
  await fleet.scrollIntoViewIfNeeded();
  await p.waitForTimeout(500);
  const box = await p.evaluate(() => { const e=document.querySelector('.fleet').closest('.sec'); const r=e.getBoundingClientRect(); return {y: r.top+scrollY}; });
  await p.evaluate(y => window.scrollTo(0, y-70), box.y);
  await p.waitForTimeout(500);
  await p.screenshot({ path: 'lab-fleet.png' });
  await b.close(); console.log('done');
})();
