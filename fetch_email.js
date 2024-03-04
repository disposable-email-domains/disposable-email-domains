const puppeteer = require("puppeteer");
const fs = require("fs");

const disposableProviders = loadFile("disposable_providers.txt");
const alowlist = loadFile("allowlist.conf");
const disposableEmailBlocklist = loadFile("disposable_email_blocklist.conf");

function loadFile(filePath) {
  const content = fs.readFileSync(filePath, "utf8");
  try {
    content
  } catch (error) {
    console.error("Error loading file:", error);
  }
  return content.split("\n");
}

function appendToFile(filePath, content) {
  fs.appendFile(filePath, content, (err) => {
    if (err) {
      console.error("Error appending to file:", err);
    }
  });
}

async function run(disposableProviders) {
  const browser = await puppeteer.launch({
    headless: true,
    defaultViewport: {
      width: 640,
      height: 480,
    },
  });

  const page = await browser.newPage();

  for (let i = 0; i < disposableProviders.length; i++) {
    const disposableProvider = disposableProviders[i];
    let input;
    try {
      await page.goto(disposableProvider, { waitUntil: "load", timeout: 3000 });
      const bodyElement = await page.$("body");
      if (!bodyElement) continue;
      input = await bodyElement.evaluate((element) => element.innerHTML);
    } catch (error) {
      if (error.constructor.name === "TimeoutError") {
        console.error("Timeout occurred while getting the link:", disposableProvider);
      } else {
        console.error("Error occurred while getting the link:", error);
      }
    }

    if (!input) continue;

    const foundDomains = fetchDisposableDomains(input, disposableProvider);

    if (foundDomains && foundDomains.length > 0) {
      console.log("Found", foundDomains, "domains on", disposableProvider);
      appendToFile('disposable_email_blocklist.conf', foundDomains.join('\n') + '\n');
    }
  }

  await browser.close();
}

function fetchDisposableDomains(input, disposableProvider) {
  const foundDomains = {};
  const emailRegex = /\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b/g;
  const emails = input.match(emailRegex);
  if (!emails || emails.length === 0) {
    console.log("No email domain found on", disposableProvider);
    return [];
  }

  const domains = emails
    .map((email) => email.split("@")[1])
    .filter((domain) => !domain.match(/\.(jpg|jpeg|png|gif)$/i));
  if (!domains || domains.length === 0) {
    console.log("No domain found on", disposableProvider);
    return [];
  }

  const foundDomainsWithNoAllowList = domains.filter((domain) => !alowlist.includes(domain));

  if (!foundDomainsWithNoAllowList || foundDomainsWithNoAllowList.length === 0) {
    console.log("No domain found on", disposableProvider);
    return [];
  }

  const foundDomainsWithoutBlockList = foundDomainsWithNoAllowList.filter((domain) => !disposableEmailBlocklist.includes(domain));


  if (!foundDomainsWithoutBlockList || foundDomainsWithoutBlockList.length === 0) {
    console.log("Domains already exist", disposableProvider);
    return [];
  }

  foundDomainsWithoutBlockList.forEach((domain) => {
    if (!domain) return;
    foundDomains[domain] = 1;
  });

  return Object.keys(foundDomains);
}

run(disposableProviders);
