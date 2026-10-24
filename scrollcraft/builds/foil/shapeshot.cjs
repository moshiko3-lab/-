const { chromium } = require('/opt/node22/lib/node_modules/playwright');
const path = require('path');
(async () => {
  const b = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium-1194/chrome-linux/chrome' });
  const p = await b.newPage({ viewport: { width: 780, height: 420 }, deviceScaleFactor: 2 });
  await p.goto('file://' + path.resolve(__dirname, 'ski-shape.html'), { waitUntil: 'networkidle' });
  await p.waitForTimeout(400);
  await p.screenshot({ path: 'ski-shape.png' });
  await b.close(); console.log('done');
})();
