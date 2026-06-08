const { chromium } = require('playwright');
const APP = 'http://localhost:5174';

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  page.setDefaultTimeout(30000);

  await page.goto(APP + '/?tauri', { waitUntil: 'domcontentloaded', timeout: 90000 });
  await page.waitForTimeout(5000);

  await page.evaluate(async () => {
    const pinia = document.querySelector('#app').__vue_app__.config.globalProperties.$pinia;
    await pinia._s.get('user').register('wz', 'test12345', '', 'WZ');
  });

  await page.goto(APP + '/edit', { waitUntil: 'domcontentloaded', timeout: 90000 });
  await page.waitForTimeout(5000);

  // Fill title/content
  await page.locator('input[placeholder*="title" i]').first().fill('ZZ Draft');
  await page.locator('textarea').first().fill('# ZZ\n\nTest.');

  // Find the commit input specifically
  const allInputs = page.locator('input');
  const count = await allInputs.count();
  console.log('Inputs found:', count);
  for (let i = 0; i < count; i++) {
    const ph = await allInputs.nth(i).getAttribute('placeholder');
    const type = await allInputs.nth(i).getAttribute('type');
    const val = await allInputs.nth(i).inputValue();
    console.log('  [' + i + '] type=' + type + ' placeholder=' + ph + ' value=' + val);
  }

  // Try filling commit message by finding the right input
  for (let i = 0; i < count; i++) {
    const ph = await allInputs.nth(i).getAttribute('placeholder') || '';
    if (ph.includes('commit') || ph.includes('Commit')) {
      await allInputs.nth(i).fill('my commit msg');
      console.log('Filled commit at [' + i + ']');
    }
  }

  // NOW click save
  await page.locator('button[aria-label="保存草稿"]').click();
  await page.waitForTimeout(4000);

  const drafts = await page.evaluate(() => {
    const r = localStorage.getItem('_t_drafts');
    console.log('_t_drafts raw:', r);
    return r ? JSON.parse(r) : [];
  });
  console.log('\nDrafts:', JSON.stringify(drafts, null, 2));

  if (drafts.length === 0) {
    await page.screenshot({ path: '/tmp/debug-inputs.png', fullPage: true });
    // Check if popup appeared
    const popup = await page.evaluate(() => {
      const els = document.querySelectorAll('.modal-overlay, [class*="popup"], [class*="commit"]');
      return Array.from(els).map(e => e.className + ': ' + e.textContent?.substring(0,100));
    });
    console.log('Overlays:', JSON.stringify(popup, null, 2));
  }

  await browser.close();
})();
