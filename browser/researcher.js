require('dotenv').config();
const fs = require('fs');
const path = require('path');
const { getBrowser } = require('./browserlessClient');
const config = require('./puppeteer.config');
const { attemptLogin } = require('./utils');

async function scrapeDigistore() {
  const browser = await getBrowser();
  const page = await browser.newPage();
  const offers = [];

  const loginUrl = 'https://www.digistore24.com/en/home/login';
  const marketplaceUrl = 'https://www.digistore24-app.com/app/en/vendor/account/marketplace/all';

  try {
    console.log("🔐 Navigating to login page...");
    await page.goto(loginUrl, config.defaultPageOptions);

    await attemptLogin(
      page,
      loginUrl,
      process.env.DIGISTORE_EMAIL,
      process.env.DIGISTORE_PASSWORD
    );

    console.log("📦 Navigating to vendor marketplace...");
    await page.goto(marketplaceUrl, config.defaultPageOptions);

    const loadedShot = path.join(__dirname, '..', 'output', 'marketplace-loaded.png');
    await page.screenshot({ path: loadedShot });
    console.log(`📸 Saved marketplace screenshot: ${loadedShot}`);
  } catch (err) {
    console.error("❌ Login or navigation failed:", err);
    await browser.close();
    return;
  }

  console.log("🔍 Scraping offer data...");
  try {
    const pageOffers = await page.evaluate(() => {
      const rows = Array.from(document.querySelectorAll('.product-box, .vendor-item'));
      return rows.map(row => {
        const title = row.querySelector('.product-title, .vendor-item__title')?.innerText.trim() || '';
        const link = row.querySelector('a')?.href || '';
        const category = row.querySelector('.category-badge')?.innerText.trim() || '';
        const commission = row.querySelector('.earnings span')?.innerText.trim() || '';
        return { title, link, category, commission };
      });
    });

    if (pageOffers.length === 0) {
      console.log("⚠️ No offers found — check selectors.");
    }

    offers.push(...pageOffers);
  } catch (err) {
    console.error("❌ Scraping error:", err);
  }

  const outputPath = path.join(__dirname, '..', 'output', 'offers.json');
  fs.mkdirSync(path.dirname(outputPath), { recursive: true });
  fs.writeFileSync(outputPath, JSON.stringify(offers, null, 2));
  console.log(`✅ Done. Scraped ${offers.length} offers to offers.json`);

  await browser.close();
}

scrapeDigistore().catch(err => {
  console.error("❌ Scraper crashed:", err);
});
