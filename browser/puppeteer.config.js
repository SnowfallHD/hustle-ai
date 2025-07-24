// browser/puppeteer.config.js

module.exports = {
  connectOptions: {
    browserWSEndpoint: `wss://chrome.browserless.io?token=${process.env.BROWSERLESS_TOKEN}`,
  },

  defaultPageOptions: {
    waitUntil: 'networkidle2',
    timeout: 60000,
    viewport: { width: 1280, height: 800 },
  },

  scrapeSettings: {
    maxPages: 15,         // max Digistore pages to scrape
    minOffersPerPage: 5,  // early stop if fewer than this
    delayBetweenPages: 1500, // in ms
  },

  retrySettings: {
    maxRetries: 3,
    retryDelay: 2000,     // in ms
  }
};
