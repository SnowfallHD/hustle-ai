const delay = ms => new Promise(resolve => setTimeout(resolve, ms));

async function handleCookies(page) {
  try {
    console.log("🍪 Checking for cookie popup...");
    const cookieBtn = await page.$('button#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll');
    if (cookieBtn) {
      await cookieBtn.click();
      console.log("✅ Cookie consent accepted.");
    } else {
      console.log("ℹ️ No cookie popup detected.");
    }
  } catch (err) {
    console.warn("❌ Error handling cookie popup:", err.message);
  }
}

async function attemptLogin(page, loginUrl, email, password, maxRetries = 3) {
  for (let attempt = 1; attempt <= maxRetries; attempt++) {
    try {
      console.log(`🔁 Attempt ${attempt} of ${maxRetries}...`);

      if (attempt > 1) {
        await page.goto(loginUrl, { waitUntil: 'domcontentloaded' });
        await delay(500 + Math.random() * 1000);
      }

      await handleCookies(page);

      // Locate fresh iframe
      await page.waitForSelector('iframe', { timeout: 5000 });
      const frameElement = await page.$('iframe');
      const frame = await frameElement.contentFrame();
      if (!frame) throw new Error("❌ Failed to acquire iframe");

      // Input email
      await frame.waitForSelector('input[name="login_username"]', { timeout: 5000 });
      await frame.focus('input[name="login_username"]');
      await page.keyboard.type(email, { delay: 15 + Math.random() * 10 });

      // Input password
      await frame.waitForSelector('input[name="login_password"]', { timeout: 5000 });
      await frame.focus('input[name="login_password"]');
      await page.keyboard.type(password, { delay: 15 + Math.random() * 10 });

      // Click login
      await frame.waitForSelector('button[name="login_login"]', { timeout: 5000 });
      await Promise.all([
        frame.click('button[name="login_login"]'),
        page.waitForNavigation({ waitUntil: 'domcontentloaded', timeout: 10000 })
      ]);

      console.log("✅ Login successful!");
      return true;

    } catch (err) {
      console.warn(`⚠️ Attempt ${attempt} failed: ${err.message}`);
      if (attempt === maxRetries) throw new Error("❌ Max login attempts exceeded.");
      await delay(2000 + Math.random() * 2000);
    }
  }
}
module.exports = { delay, handleCookies, attemptLogin };
