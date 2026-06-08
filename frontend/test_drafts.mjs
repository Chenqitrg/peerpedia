import { chromium } from 'playwright';

const APP = 'http://localhost:5173';

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();

  // Step 1: Load app with ?tauri
  console.log('1. Loading app...');
  await page.goto(APP + '?tauri', { waitUntil: 'networkidle', timeout: 15000 });
  await page.waitForTimeout(1500);

  // Step 2: Click login button to open modal
  console.log('2. Opening auth modal...');
  await page.click('button:has-text("Login")');
  await page.waitForTimeout(500);

  // Switch to Register tab using JS click (bypasses overlay issue)
  await page.evaluate(() => {
    const buttons = document.querySelectorAll('button');
    for (const btn of buttons) {
      if (btn.textContent?.includes('注册') || btn.textContent?.includes('Register')) {
        (btn as HTMLElement).click();
        break;
      }
    }
  });
  await page.waitForTimeout(500);
  console.log('   Switched to Register tab');

  // Fill registration form
  const inputs = page.locator('input');
  const count = await inputs.count();
  console.log('   Found', count, 'inputs');
  for (let i = 0; i < count; i++) {
    const placeholder = await inputs.nth(i).getAttribute('placeholder');
    console.log('   Input', i, ':', placeholder);
  }
  
  // Try common selectors
  const allInputs = page.locator('form input');
  const allCount = await allInputs.count();
  if (allCount >= 2) {
    await allInputs.nth(0).fill('testwriter');
    await allInputs.nth(1).fill('test123');
    if (allCount >= 3) await allInputs.nth(2).fill('Test Writer');
    console.log('   Filled registration form');
  }

  // Submit - find the submit button
  await page.evaluate(() => {
    const buttons = document.querySelectorAll('button');
    for (const btn of buttons) {
      const text = btn.textContent || '';
      if (text.includes('创建') || text.includes('Create') || text.includes('Register')) {
        (btn as HTMLElement).click();
        break;
      }
    }
  });
  await page.waitForTimeout(2000);
  console.log('   Submitted registration');

  // Step 3: Check state
  const viewer = await page.evaluate(() => {
    const raw = localStorage.getItem('viewer');
    return raw ? JSON.parse(raw) : null;
  });
  console.log('3. Viewer:', viewer ? viewer.username + ' (' + viewer.id + ')' : 'NULL');

  const token = await page.evaluate(() => localStorage.getItem('peerpedia_local_token'));
  console.log('   Token:', token ? token.substring(0,12) + '...' : 'NULL');

  if (!viewer) {
    console.log('ERROR: Registration failed - no viewer in localStorage');
    await page.screenshot({ path: '/tmp/reg-failed.png', fullPage: true });
    await browser.close();
    process.exit(1);
  }

  // Step 4: Navigate to editor and create draft
  console.log('4. Creating draft in editor...');
  await page.goto(APP + '/editor', { waitUntil: 'networkidle', timeout: 15000 });
  await page.waitForTimeout(1500);

  // Fill title
  await page.evaluate(() => {
    const inputs = document.querySelectorAll('input[type="text"]');
    for (const inp of inputs) {
      const placeholder = (inp as HTMLInputElement).placeholder?.toLowerCase() || '';
      if (placeholder.includes('title') || placeholder.includes('标题')) {
        (inp as HTMLInputElement).value = 'Hello Playwright Draft';
        inp.dispatchEvent(new Event('input', { bubbles: true }));
        break;
      }
    }
  });

  // Fill content
  await page.evaluate(() => {
    const textareas = document.querySelectorAll('textarea');
    for (const ta of textareas) {
      (ta as HTMLTextAreaElement).value = '# Hello World\n\nThis is a Playwright test draft.';
      ta.dispatchEvent(new Event('input', { bubbles: true }));
      break;
    }
  });

  // Fill commit message
  await page.evaluate(() => {
    const inputs = document.querySelectorAll('input');
    for (const inp of inputs) {
      const placeholder = (inp as HTMLInputElement).placeholder?.toLowerCase() || '';
      if (placeholder.includes('commit')) {
        (inp as HTMLInputElement).value = 'initial commit';
        inp.dispatchEvent(new Event('input', { bubbles: true }));
        break;
      }
    }
  });

  await page.waitForTimeout(500);

  // Click save button
  await page.evaluate(() => {
    const buttons = document.querySelectorAll('button');
    for (const btn of buttons) {
      const label = btn.getAttribute('aria-label') || btn.getAttribute('title') || '';
      if (label.toLowerCase().includes('save')) {
        (btn as HTMLElement).click();
        break;
      }
    }
  });
  await page.waitForTimeout(2000);
  console.log('   Save clicked');

  // Step 5: Check draft saved
  const drafts = await page.evaluate(() => {
    const raw = localStorage.getItem('_t_drafts');
    return raw ? JSON.parse(raw) : null;
  });
  console.log('5. _t_drafts:', drafts ? drafts.length + ' drafts' : 'NULL');
  if (drafts) drafts.forEach(d => console.log('   - id:', d.id, '| title:', d.title, '| account_id:', d.account_id));

  // Step 6: Navigate to user page
  console.log('6. Navigating to user page...');
  await page.goto(APP + '/user/' + viewer.id, { waitUntil: 'networkidle', timeout: 15000 });
  await page.waitForTimeout(2000);

  await page.screenshot({ path: '/tmp/userpage-final.png', fullPage: true });
  const pageText = await page.textContent('body');
  console.log('   Has "Hello Playwright Draft":', pageText.includes('Hello Playwright Draft'));
  console.log('   Has "No articles":', pageText.toLowerCase().includes('no article'));
  console.log('   Screenshot: /tmp/userpage-final.png');

  await browser.close();
  console.log('\nDone.');
})();
