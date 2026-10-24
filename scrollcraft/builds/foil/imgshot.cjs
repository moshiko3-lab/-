const { chromium } = require('/opt/node22/lib/node_modules/playwright');
const path = require('path');
(async () => {
  const b = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium-1194/chrome-linux/chrome' });
  const p = await b.newPage({ viewport: { width: 1080, height: 1200 }, deviceScaleFactor: 1.5 });
  await p.goto('file://' + path.resolve(__dirname, 'img-test.html'), { waitUntil: 'networkidle' });
  await p.waitForTimeout(600);
  await p.screenshot({ path: 'img-test.png', fullPage: true });
  await b.close(); console.log('done');
})();
