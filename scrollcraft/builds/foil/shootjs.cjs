const { chromium } = require('/opt/node22/lib/node_modules/playwright');
const path = require('path');
(async () => {
  const b = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium-1194/chrome-linux/chrome' });
  const p = await b.newPage({ viewport: { width: 1100, height: 760 }, deviceScaleFactor: 2 });
  await p.goto('file://' + path.resolve(__dirname, 'jetski.html'), { waitUntil: 'networkidle' });
  await p.waitForTimeout(700);
  await p.screenshot({ path: 'jetski.png' });
  await b.close(); console.log('done');
})();
