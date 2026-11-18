// Optional browser QA. Runtime inspection has no Node or browser-package dependency.
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

(async () => {
  const output = process.env.INSPECTION_QA_OUT || 'data/phase3-inspection';
  fs.mkdirSync(output, { recursive: true });
  const browser = await chromium.launch({headless: true,
    ...(process.env.CHROMIUM_PATH ? {executablePath: process.env.CHROMIUM_PATH} : {})});
  try {
    const page = await browser.newPage({viewport: {width: 1440, height: 900}});
    const failures = [];
    page.on('pageerror', e => failures.push(e.message));
    await page.goto(process.env.INSPECTION_URL || 'http://127.0.0.1:8765');
    await page.waitForFunction(() => document.querySelector('#status').textContent.includes('measured source'), {timeout: 30000});
    await page.locator('#placement').selectOption({index: 1});
    assert.match(await page.locator('#mount-description').textContent(), /30%/);
    await page.locator('#play').click();await page.waitForTimeout(300);await page.locator('#play').click();
    assert.notEqual(await page.locator('#time').textContent(), '0.00 s');
    await page.locator('#reset').click();assert.equal(await page.locator('#time').textContent(), '0.00 s');
    await page.locator('#motion-mode').selectOption('optical');
    assert.match(await page.locator('#motion-status').textContent(), /does not establish time alignment/);
    await page.locator('summary').click();await page.locator('#rotation').fill('30');await page.locator('#seed').fill('23');
    await page.locator('#apply').click();
    await page.waitForFunction(() => !document.querySelector('#apply').disabled);
    const provenance = JSON.parse(await page.locator('#provenance').textContent());
    assert.equal(provenance.seed, 23);assert.equal(provenance.config.orientation.max_degrees, 30);
    const downloaded = page.waitForEvent('download');await page.locator('#export').click();
    await (await downloaded).saveAs(path.join(output, 'verified-preview.json'));
    await page.screenshot({path:path.join(output, 'desktop.png'), fullPage:true});
    await page.locator('#seed').fill('-1');await page.locator('#apply').click();
    await page.waitForFunction(() => !document.querySelector('#error').hidden);
    assert.match(await page.locator('#error').textContent(), /Seed|seed/);
    assert.equal(await page.locator('#play').isDisabled(), true);
    await page.locator('#seed').fill('23');await page.locator('#apply').click();
    await page.waitForFunction(() => !document.querySelector('#apply').disabled);
    await page.setViewportSize({width:390,height:844});
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),true);
    await page.screenshot({path:path.join(output,'mobile.png'),fullPage:true});
    for(const canvas of await page.locator('canvas').all()) {
      const size = await canvas.evaluate(c => [c.width,c.height]);
      assert(size[0]>100 && size[1]>50);
    }
    assert.deepEqual(failures,[]);
    console.log('PASS: desktop/mobile render; no horizontal overflow; six trace canvases and arm; mount switch, optical-board view with unaligned clocks, play/pause/reset, seeded configuration, JSON export, invalid-seed error/recovery; no page errors');
    console.log(`Screenshots and exported preview: ${output}`);
  } finally {await browser.close();}
})().catch(error => {console.error(error);process.exitCode=1;});
