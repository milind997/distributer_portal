import { chromium } from "@playwright/test";
import fs from "node:fs";
const work =
  process.env.DP_TEST_WORKDIR || new URL("../test-results/", import.meta.url).pathname;
const base = "http://distributor-portal-test.localhost:8001";
const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({
  viewport: { width: 1440, height: 1000 },
});
const page = await context.newPage();
const errors = [];
page.on("pageerror", (e) => errors.push(e.message));
page.on("response", (r) => {
  if (r.status() >= 400 && !r.url().includes("favicon"))
    errors.push(r.status() + " " + r.url());
});
await page.goto(base + "/login");
const loginStatus = await page.evaluate(
  async (password) =>
    (
      await fetch("/api/method/login", {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: new URLSearchParams({ usr: "Administrator", pwd: password }),
      })
    ).status,
  fs.readFileSync(work + "/test-admin-password", "utf8"),
);
if (loginStatus !== 200)
  throw new Error("Test-site login failed: " + loginStatus);
await page.goto(base + "/distributor");
await page.getByRole("heading", { name: "Overview", exact: true }).waitFor();
await page.waitForSelector(".stats");
await page.screenshot({ path: work + "/portal-desktop.png", fullPage: true });
for (const [route, title] of [
  ["orders", "Orders"],
  ["stock", "My stock"],
  ["sales", "Record sales"],
  ["declarations", "Stock declarations"],
  ["returns", "Returns & damage"],
  ["accounts", "Account & credit"],
  ["forecast", "Forecast"],
  ["outlets", "Outlets"],
  ["network", "Network overview"],
  ["flags", "Territory flags"],
  ["partners", "Channel partners"],
  ["settings", "Portal settings"],
]) {
  await page.goto(base + "/distributor/" + route);
  await page.getByRole("heading", { name: title, exact: true }).waitFor();
  await page.waitForFunction(() => !document.querySelector(".loading"));
  if (await page.locator("[role=alert]").count())
    errors.push(
      route + ": " + (await page.locator("[role=alert]").first().innerText()),
    );
}
await page.goto(base + "/distributor");
await page.waitForSelector(".stats");
await page.setViewportSize({ width: 390, height: 844 });
await page.waitForFunction(
  () => document.querySelector(".sidebar").getBoundingClientRect().right <= 0,
);
await page.screenshot({ path: work + "/portal-mobile.png", fullPage: true });
const overflow = await page.evaluate(
  () => document.documentElement.scrollWidth > innerWidth,
);
if (overflow) errors.push("Mobile viewport overflow");
await page.getByRole("button", { name: "Open navigation" }).click();
await page.getByRole("button", { name: "Orders", exact: true }).click();
await page.getByRole("heading", { name: "Orders", exact: true }).waitFor();
console.log(
  JSON.stringify(
    { errors, mobileOverflow: overflow, routesChecked: 13 },
    null,
    2,
  ),
);
await browser.close();
if (errors.length) process.exitCode = 1;
