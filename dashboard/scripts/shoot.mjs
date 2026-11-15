// Captura de pantalla amb espera real (per a mapes amb Web Worker com MapLibre).
// Ús: node scripts/shoot.mjs <url> <out.png> [waitMs] [height]
import puppeteer from "puppeteer-core";

const [url, out, waitMs = "7000", height = "1280"] = process.argv.slice(2);
const CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";

const browser = await puppeteer.launch({
  executablePath: CHROME,
  headless: "new",
  args: ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--hide-scrollbars", "--no-sandbox"],
  defaultViewport: { width: 1440, height: Number(height), deviceScaleFactor: 1 },
});
const page = await browser.newPage();
const errs = [];
page.on("console", (m) => { if (m.type() === "error") errs.push(m.text()); });
await page.goto(url, { waitUntil: "networkidle2", timeout: 60000 });
await new Promise((r) => setTimeout(r, Number(waitMs)));
await page.screenshot({ path: out });
if (errs.length) console.log("page errors:", errs.slice(0, 5).join(" | "));
console.log("saved", out);
await browser.close();
