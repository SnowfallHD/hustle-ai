const puppeteer = require('puppeteer-firefox');
const StealthPlugin = require('puppeteer-extra-plugin-stealth');
puppeteer.use(StealthPlugin());

async function getBrowser() {
  const browser = await puppeteer.launch({
    headless: false,                      // 👁️ Show browser window
    slowMo: 75,                           // 🐢 Slow down for visibility
    defaultViewport: null,               // 🖥️ Use full window
    args: ['--start-maximized'],         // 🧱 Launch full screen
  });
  return browser;
}

module.exports = { getBrowser };
