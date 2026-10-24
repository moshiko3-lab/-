const { chromium } = require('/opt/node22/lib/node_modules/playwright');
const path = require('path');
(async () => {
  const b = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium-1194/chrome-linux/chrome' });
  const ctx = await b.newContext({ viewport: { width: 1040, height: 560 }, recordVideo: { dir: 'vid', size: { width: 1040, height: 560 } } });
  const p = await ctx.newPage();
  await p.goto('file://' + path.resolve(__dirname, 'jetski.html'), { waitUntil: 'networkidle' });
  await p.evaluate(() => window.scrollTo(0, 150));
  await new Promise(r => setTimeout(r, 5200));
  await p.close(); await ctx.close(); await b.close();
  console.log('recorded');
})();
